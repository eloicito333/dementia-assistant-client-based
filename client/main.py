from transcriber import Transcriber, transcriber_utils
from recorder import Recorder
from handler import Handler
from main_assistant import MainAssistant
from player import AudioPlayer

from essential_data import USER_GENDER, USER_NAME, ASSISTANT_NAME

transcriber_options = {
    "language": "ca",
    "prompt": transcriber_utils.generate_prompt(user_name=USER_NAME, user_gender=USER_GENDER, assistant_name=ASSISTANT_NAME)
}

def main():
    #initialize player
    audio_player = AudioPlayer()

    #initialize assistant
    main_assistant = MainAssistant(name=ASSISTANT_NAME, audio_player=audio_player)

    #initialize the transcription handler
    handler= Handler(assistant=main_assistant)

    # Initialize the Transcriber
    transcriber = Transcriber()

    # Initialize and start the Recorder
    recorder = Recorder(transcriber=transcriber, transcriber_options=transcriber_options, result_handler=handler, audio_player=audio_player, verbose=True)
    recorder.start()
    

if __name__ == "__main__":
    main()