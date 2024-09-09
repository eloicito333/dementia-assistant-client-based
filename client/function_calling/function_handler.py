from function_calling.vector_data_retrieval import VectorDataRetrieval
from function_calling.function_parent_class import OpenAIFunction

import json
from threading import Thread

class FunctionHandler:
    def __init__(self):
        self.handler_array= [VectorDataRetrieval()]

        self.handlers = dict(zip([handler.getName() for handler in self.handler_array], self.handler_array))

        print(list(self.handlers.values()))
        self.tools_array =  [self._description_to_tools(tool) for tool in self.handlers.values()] #map(list(self.handlers.values()), self._description_to_tools)
    
    def get_tools_array(self):
        return self.tools_array

    def _description_to_tools(self, function: OpenAIFunction) -> dict[str, str]:
        return {
                "type": "function",
                "function": function.description
            }
    
    def _handle_tool_call(self, index, tool_call, results):
        result = self.handlers[tool_call["function"]["name"]].apply(json.loads(tool_call["function"]["arguments"]))
        results[index] = result
        return result

    
    def handle(self, message):
        print("FUNCTION HANDLEING: ", message)
        results = [None] * len(message.tool_calls)
        threads = []

        for index, tool_call in enumerate(message.tool_calls):
            thread = Thread(target=self._handle_tool_call, args=(index, tool_call, results))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        result_messages = [{
            "role": "tool",
            "content": json.dumps(result),
            "tool_call_id": message.tool_calls[index].id
        } for index, result in enumerate(results)]

        print(result_messages)

        return result_messages