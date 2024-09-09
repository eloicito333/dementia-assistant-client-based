from openai_client import OPENAI_CLIENT
import datetime

from utils import get_subscriptable
from transcriber import transcriber_utils
from essential_data import USER_GENDER, USER_NAME
from function_calling.function_handler import FunctionHandler
from api_helper import api_helper
from threading import Thread

class ContextWindow:
    def __init__(self, max_tokens=100_000):
        self.max_tokens = max_tokens

        self.current_usage_tokens = 0
        self.context_window = []
        self.system_message = {"content": "", "usage": 0}

        self.final_messages = []

    def _estimate_usage(self, text):
        return len(text) * .25
        
    def add_message(self, message, usage=None):
        if(not usage):
            usage = self._estimate_usage(message["content"])
        
        print("message role: ", get_subscriptable(message, "role"), message)
        if get_subscriptable(message, "role") == "system":
            if(self.system_message): self.current_usage_tokens -= self.system_message["usage"]
            self.system_message = {
                "message": message,
                "usage": usage
            }
            self.current_usage_tokens += usage

        else:
            self.context_window.append({
                "message": message,
                "usage": usage
            })

        total_tokens = self.system_message["usage"]
        truncation_index = 0
        for message in self.context_window:
            total_tokens += message["usage"]
        
        if(total_tokens > self.max_tokens):
            for i in range(0, len(self.context_window)):
                total_tokens -= self.context_window[i]
                if(not total_tokens > self.max_tokens):
                    truncation_index = i + 1
                    break
        
        self.final_messages = [self.system_message.get("message")] + [message["message"] for message in self.context_window][truncation_index:]

        self.current_usage_tokens = total_tokens

    def get_messages(self):
        return self.final_messages
    
    def clear(self):
        self.current_usage_tokens = 0
        self.context_window = []

        self.final_messages = []


class MainAssistant:
    def __init__(self, name, audio_player):
        self.audio_player = audio_player
        self.name = name

        self.client = OPENAI_CLIENT

        self.last_interaction = None
        self.is_interacting = False

        self.context_window = ContextWindow()

        self.system_prompts = {
            "normal": f"""Ets en {self.name}, un assistent de veu disenyat per ajudar i millorar l'autonomia de les persones amb demència. Ets calmat, relaxat, i actues amb paciència.
{transcriber_utils.get_name_with_article(USER_NAME, USER_GENDER)[0].upper() + transcriber_utils.get_name_with_article(USER_NAME, USER_GENDER)[1:]} és el/la teu pacient. El seu gènere és {USER_GENDER}.
La teva funció és ajudar-lo en tot el que li faci falta, sent conscient que molts cops oblidarà el que s'ha parlat.
Les teves respostes han de ser donades a partir de l'informació que tens a l'abast (dins d'aquest context). Si necessites informació fora d'aquest context, pots utilitzar les eines que tens al teu abast, com per exemple "internal_data_search"."""
        }

        self.function_handler = FunctionHandler()

    def save_to_db(self, text, speaker, inConversation, confidential=None):
        args={
            "text": text,
            "speaker": speaker,
            "date": datetime.datetime.now().isoformat(),  # ISO 8601 format
            "confidential": confidential,
            "inConversation": inConversation
        }
        thread = Thread(name="Posting spoken text", target=api_helper.spoken_data_db.post_document, args=(args,))
        thread.start()
        return thread

    def _detect_awaken(self, text):
        return self.name in text
    
    def _talk(self, text):
        self.audio_player.tts_and_play_in_thread(text)
        print("TALKING: ", text)

    def _conversate(self, metadated_text, speaker, confidential, mode="normal", temperature=.6):
        print("conversate")
        self.save_to_db(text=metadated_text["text"], speaker=speaker, inConversation=True, confidential=confidential)
        print("storing initialitzed")

        self.is_interacting = True
        self.context_window.add_message({
            "role": "system",
            "content": self.system_prompts[mode]
        })
        self.context_window.add_message({
            "role": "user",
            "content": metadated_text["text"]
        }, usage=metadated_text["tokens"])
        
        finish_reason = None
        finish_reasons_to_continue = ["tool_calls", "function_call"]

        while not finish_reason or finish_reason in finish_reasons_to_continue:
            print("conversation messages: ", self.context_window.get_messages())
            response = self.client.chat.completions.create(
                model="gpt-4o",
                temperature=temperature,
                messages=self.context_window.get_messages(),
                tools=self.function_handler.get_tools_array()
            )

            finish_reason = response.choices[0].finish_reason

            if finish_reason == None:
                self.talk("No hi ha bona connexió a internet!")
                break

            self.context_window.add_message(response.choices[0].message, usage=response.usage.completion_tokens)

            if finish_reason == "tool_calls" or finish_reason == "function_call":
                messages = self.function_handler.handle(response.choices[0].message)
                for message in messages: self.context_window.add_message(message)
            
            elif finish_reason == "stop":
                self._talk(response.choices[0].message.content)


        self.last_interaction = datetime.datetime.now()


    def handle(self, metadated_text, confidential, speaker):
        text = metadated_text["text"]

        #see if there has been recent interaction (continue conversation)
        if(self.is_interacting or (self.last_interaction and (datetime.datetime.now() - self.last_interaction) < datetime.timedelta(seconds=30))):
            self._conversate(metadated_text, speaker=speaker, confidential=confidential)

        #see if new conversation starts
        elif(self._detect_awaken(text)):
            self.context_window.clear()
            self._conversate(metadated_text, speaker=speaker, confidential=confidential)

        else:
            self.save_to_db(text=text, speaker=speaker, inConversation=False, confidential=confidential)
