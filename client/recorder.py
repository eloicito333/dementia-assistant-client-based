import sounddevice as sd
import soundfile as sf
import queue
import os
import numpy as np
import tempfile
import threading

from transcriber import transcriber_utils
from main_assistant import MainAssistant

from essential_data import USER_GENDER, USER_NAME, ASSISTANT_NAME

transcriber_options = {
    "language": "ca",
    "prompt": transcriber_utils.generate_prompt(user_name=USER_NAME, user_gender=USER_GENDER, assistant_name=ASSISTANT_NAME)
}

# Constants

Vocals: list[int] = [50, 1000]  # Frequency range to detect sounds that could be speech

SampleRate = 16000  # Stream device recording frequency per second
BlockSize = 30  # Block size in milliseconds

# 33 blocks = 1 second (aprox)
EndBlocks = 50  # ~33x1,5 Number of blocks to wait before sending (30 ms is block)
FlushBlocks = 33 * 25  # Number of blocks to wait before sending
ConnectionBlocks = 33 * 5 # Number of blocks to start saving the audio data to a new buffer before sending in order to preserve context


class AudioBuffer:
    def __init__(self, number, audio_player):
        self.audio_player = audio_player
        self.number = number

        self.buffer = queue.Queue()
        self.temp = tempfile.NamedTemporaryFile(prefix="recorder_",suffix=".wav", delete=False)
        self.file = sf.SoundFile(self.temp.name, mode='w', samplerate=SampleRate, channels=1)
        self.opened_file = None

        self.blocks_speaking = FlushBlocks

        self.context_prompt = None
        self.continuation = False

        print(self.temp.name)
        

    def save_to_file(self):
        for _ in range(0, self.buffer.qsize()):
            self.file.write(self.buffer.get())
            print("|", end="", flush=True)

    
    def put(self, data):
        self.buffer.put(data)
        self.blocks_speaking -= 1

        """ if FlushBlocks - self.blocks_speaking > 50: # 1,5 sec aprox.
            self.audio_player.stop() """
    
    def get_file_content(self):
        self.save_to_file()
        self.opened_file = open(self.temp.name, "rb")
        return self.opened_file

    def terminate(self):
        if self.opened_file:
            self.opened_file.close()

        self.file.close()
        self.temp.close()
        # Make sure to delete the temporary file when done
        """ try:
            os.remove(self.temp.name)
        except Exception as e:
            print(f"Could not delete temp file: {e}") """


class Recorder:
    def __init__(self, transcriber, transcriber_options, result_handler, audio_player, threshold=0.01, input_device=None, verbose=False):
        self.audio_player = audio_player

        self.transcriber = transcriber
        self.threshold = threshold
        self.verbose = verbose
        self.input_device = input_device
        
        self.running = True
        self.waiting = 0
        self.buffers = [AudioBuffer(number=0, audio_player=self.audio_player), AudioBuffer(number=1, audio_player=self.audio_player)]
        self.buffer_counter = 2
        self.speaking = False
        self.blocks_speaking = 0
        self.buffers_to_process = []

        self.transcriber_options = transcriber_options

        self.result_handler = result_handler

    def _is_there_voice(self, indata, frames):
        freq = np.argmax(np.abs(np.fft.rfft(indata[:, 0]))) * SampleRate / frames
        volume = np.sqrt(np.mean(indata**2))

        return volume > self.threshold and Vocals[0] <= freq <= Vocals[1]
    
    # method to pop and populate buffer array at once
    def _pop_buffer(self, number):
        poped_buffer=self.buffers.pop(number)

        #creating new buffer on index 1
        self.buffers.append(AudioBuffer(number=self.buffer_counter, audio_player=self.audio_player))
        self.buffer_counter+=1

        return poped_buffer
    
    def _save_to_process(self, continuation=False):

        self.buffers[0].continuation = continuation
        self.speaking = continuation

        #sending and deliting current buffer
        current_buffer=self._pop_buffer(0)
        self.buffers_to_process.append(current_buffer)

        if not continuation:
            self._pop_buffer(0)

    def _save_to_buffer(self, indata):
        self.buffers[0].put(indata)
        # save data to 2nd buffer if the 1st about to get full
        if(self.buffers[0].blocks_speaking - ConnectionBlocks) < 1:
            self.buffers[1].put(indata)
        
        #check if buffer is full to process it
        if self.buffers[0].blocks_speaking < 1:
            self._save_to_process(continuation=True)

            
    def callback(self, indata, frames, _time, status):
        if not any(indata):
            return
        
        voice = self._is_there_voice(indata, frames)

        if not voice and not self.speaking:
            return
        
        if voice:  # User speaking
            if self.verbose:
                print(".", end="", flush=True)

            self._save_to_buffer(indata)
            self.waiting = EndBlocks

            self.speaking = True
        else:  # Silence after user has spoken
            self.waiting -= 1
            if self.waiting < 1:
                self._save_to_process(continuation=False)
                self.speaking = False
                return
            else:
                if self.verbose:
                    print("-", end="", flush=True)
                
                self._save_to_buffer(indata)

    def process(self):
        if len(self.buffers_to_process) > 0:
            buffer: AudioBuffer = self.buffers_to_process.pop(0)
            file = buffer.get_file_content()
            if self.verbose:
                print("\n\033[90mTranscribing..\033[0m")

            #generating correct transcription prompt
            prompt = self.transcriber_options["prompt"] or ""
            if buffer.context_prompt:
                prompt += " " + buffer.context_prompt

            result = self.transcriber.transcribe(
                audio_data=file,
                language=self.transcriber_options["language"] or "ca",
                prompt=prompt,
                continuation=buffer.continuation,
            )

            buffer.terminate()

            if not buffer.continuation:
                if self.verbose: print(f"\033[1A\033[2K\033[0G{result}")
                else:
                    print("")
            
                self.result_handler.handle(result, speaker=USER_NAME.split(" ")[0])
            elif buffer.number + 1 == self.buffers[0].number:

                #split the string in the best way possible in order for it to be between 5 and 30 characters
                context = result.split(".")[-1]
                if len(context) > 30 or len(context) < 5:
                    context = result.split(",")[-1]
                if len(context) > 30 or len(context) < 5:
                    context = result[-30:]

                self.buffers[0].context_prompt = context

    def listen(self):
        show_device = (
            self.input_device if self.input_device is not None else sd.default.device[0]
        )
        print(
            f"\033[32mLive stream device: \033[37m{sd.query_devices(device=show_device)['name']}\033[0m"
        )
        print("\033[32mListening.. \033[37m(Ctrl+C to Quit)\033[0m")

        with sd.InputStream(
            channels=1,
            callback=self.callback,
            blocksize=int(SampleRate * BlockSize / 1000),
            samplerate=SampleRate,
            device=self.input_device,
        ):
            while self.running:
                for buffer in self.buffers:
                    buffer.save_to_file()
                
                if len(self.buffers_to_process) > 0: threading.Thread(target=self.process, name="AIAssistant_processing_audio").start()

    def start(self):
        try:
            self.listen()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            print("\n\033[93mQuitting..\033[0m")