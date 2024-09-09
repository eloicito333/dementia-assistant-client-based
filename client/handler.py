from pydantic import BaseModel
from typing import Optional
import re
import uuid

import datetime
from api_helper import api_helper
from openai_client import OPENAI_CLIENT

"""Ets una màquina que ha de cercar en el text contingut confidencial (números de compte bancari, números de targeta, etc.), substitueix-lo per un nom que el representi, posat entre <<nom clau>>. Llavors afegeix al diccionari una sortida ("confidential") el nom clau i el seu contingut com a valor. En el cas que no hi hagi contingut confidencial, deixa la clau "confidential" buida. Assegura't que el text que censuris sigui realment confidencal (normalment dades bancàries) sense preguntar a l'usuari i que el nom que li poses sigui descriptiu: NUMERO_TARGETA_BANCARIA, PIN_TARGETA_DE_CREDIT.
        NO HAS DE RESPONDRE CAP MISSATGE, SIMPLEMENT FER LA TASCA QUE SE T'HA EXPLICAT"""

class OutputFormat(BaseModel):
    corrected_text: str
    confidential: Optional[dict[str, str]]

class Handler:
    def __init__(self, assistant):
        self.client = OPENAI_CLIENT
        self.assistant = assistant
        
        self.OutputFormat = OutputFormat

    def _convert_confidential_keys(self, cured_text_obj: OutputFormat, speaker): 
        text = cured_text_obj.corrected_text
        confidential = cured_text_obj.confidential

        print("text: ", type(text), "confidential: ", type(confidential))
        if not confidential: return cured_text_obj

        new_confidential= {}

        def replace_placeholder(text: str, replacement_func):
            # This regex pattern matches substrings in the format <<something>>
            pattern = r'<<(.+?)>>'
            
            # Function to replace the matched pattern with the result from replacement_func
            def replacer(match):
                # Extract the 'something' part (inside the << >>)
                something = match.group(1)
                # Pass 'something' to the replacement function and return the result
                return replacement_func(something)

            # Use re.sub to find and replace all <<something>> with the result of replacement_func
            return re.sub(pattern, replacer, text)
        
        def replace_fn(key):
            new_key = "<<" + speaker.strip().upper().replace(" ", "_") + "_" + key.upper().strip().replace(" ", "_") + "_" + str(uuid.uuid4().int)[:4] + ">>"

            new_confidential[new_key] = confidential[key]
            return new_key
        
        new_text = replace_placeholder(text, replace_fn)

        var= OutputFormat(
            corrected_text = new_text,
            confidential = new_confidential
        )
        print(var)
        return var
    
    def _eliminate_confidentiality(self, text, speaker, temperature=.6):
        system_prompt= """A continuació es mostraran uns missatges procedents de la veu enregistrada de l'usuari. En aquests missatges és possible que aparegui contingut confidencial (números de compte bancari, números de targeta, número de DNI, etc.).
Els passos per acomplir aquesta tasca són:
    - Identificar el contingut confidencial
    - Assegurar-se que realment és confidencial
    - Substituir el contingut confidencial per un nom que el representi, posat entre <<nom clau>>.
    - Assegurar-se que el nom sigui ben descriptiu: NUMERO_TARGETA_BANCARIA, PIN_TARGETA_DE_CREDIT.
    - Afegir el nom clau com a clau al diccionari de sortida ("confidential") i al valor que oculta com el seu valor.
 
En el cas que no hi hagi contingut confidencial, s'ha de deixar la clau "confidential" buida.
Els missatges rebuts per dur a terme aquesta feina van dirigits a una tercera persona, així que no han de ser resposts, només s'ha d'analitzar la seva confidencialitat."""
        result = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": text
                }
            ],

            response_format=self.OutputFormat
        )

        parsed: OutputFormat = result.choices[0].message.parsed

        new_parsed = self._convert_confidential_keys(parsed, speaker=speaker)
        print(new_parsed)
        return new_parsed
    
    def handle(self, metadated_text, speaker): 
        text = metadated_text["text"]     
        if (not len(text)): return

        cured_text_obj = self._eliminate_confidentiality(text=text, speaker=speaker)

        new_metadated_text = {
            "text": cured_text_obj.corrected_text,
            "tokens": metadated_text["tokens"]
        }
        self.assistant.handle(new_metadated_text, confidential=cured_text_obj.confidential, speaker=speaker)