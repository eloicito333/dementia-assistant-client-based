import sounddevice as sd
import soundfile as sf
import tempfile
import os
import threading

from openai_client import OPENAI_CLIENT
from essential_data import ASSISTANT_VOICE

class AudioPlayer:
    def __init__(self, voice=ASSISTANT_VOICE):
        self.voice = voice

        self.stream = None
        self.playing = False
        self.stop_flag = False

        self.temp = None
        self.file = None

        self.client = OPENAI_CLIENT
    
    def _new_temp_file(self):
        #delete previous temp file
        self._delete_temp_file()

        #Create a temporary file to store audio data.
        self.temp = tempfile.NamedTemporaryFile(prefix="player_", suffix=".mp3", delete=False)


    def _delete_temp_file(self):
        if self.file:
            self.file.close()
            self.file = None

        if self.temp:
            self.temp.close()

            # Make sure to delete the temporary file when done
            try:
                os.remove(self.temp.name)
            except Exception as e:
                print(f"Could not delete temp file: {e}") 
            finally:
                self.temp=None

    def tts_and_play(self, text, voice=None):
        self.stop()
        self.stop_flag = False
        print("playing", self.stop_flag)
        
        self._new_temp_file()

        response = self.client.audio.speech.create(
        model="tts-1",
        voice=voice or self.voice,
        input=text
        )

        response.stream_to_file(self.temp.name)
        if(self.stop_flag): return self._delete_temp_file()

        self.play(self.temp.name)

    def play(self, file_path):
        self.stop_flag = False

        print("playing", self.stop_flag)
        #Play audio from file_path.
        self.playing = True
        #try:
            # Open audio file with soundfile for real-time processing
        self.file = sf.SoundFile(file_path, mode="r")

        blocksize=1024
        with sd.OutputStream(samplerate=self.file.samplerate, channels=self.file.channels, blocksize=blocksize) as self.stream:
            for block in self.file.blocks(blocksize=blocksize):  # Read audio in chunks (frames)
                if self.stop_flag:
                    self.stop_flag = False
                    break  # Stop playback if stop flag is triggered
                    
                #Ensure block is of type float32
                if block.dtype != 'float32':
                    block = block.astype('float32')
                print(f"Block shape: {block.shape}, dtype: {block.dtype}")
                self.stream.write(block)  # Play chunk of audio

        """ except Exception as e:
            print(f"Error during playback: {e}")
        finally:
            self.playing = False """

    def stop(self):
        """Stop the currently playing audio."""
        if self.stream:
            self.stop_flag = True
            self.stream.abort()  # Stop the stream immediately
            self._delete_temp_file()  # Delete temporary file
            print("Audio playback stopped.")

    def tts_and_play_in_thread(self, text, voice=None, final_fn=lambda: None):
        def thread_function():
            self.tts_and_play(text, voice=voice)
            final_fn()
        
        thread = threading.Thread(target=thread_function)
        thread.start()

        return thread