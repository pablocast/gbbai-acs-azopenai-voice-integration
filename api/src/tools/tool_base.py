from abc import ABC, abstractmethod
import json


class OpenAIToolBase(ABC):
    """
    Abstract base class for tools used with OpenAI function calling.
    """

    def __init__(self, name: str, description: str, **kwargs):
        """
        Initialize the tool with its name, description, and optional parameters.

        :param name: The name of the tool.
        :param description: A brief description of the tool's functionality.
        :param kwargs: Optional parameters for configuring the tool.
        """
        self.name = name
        self.description = description
        self.config = kwargs

    @abstractmethod
    def run(self, *args, **kwargs):
        """
        Execute the tool's functionality. Derived classes must implement this.

        :param args: Positional arguments for the tool's logic.
        :param kwargs: Keyword arguments for the tool's logic.
        :return: The result of the tool's execution.
        """
        pass

    def to_json(self):
        """
        Convert the tool's metadata and callable structure into JSON format
        for OpenAI function calling.

        :return: A JSON-compatible dictionary representing the tool.
        """
        tool_dict = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            },
        }
        return json.dumps(tool_dict)

    @abstractmethod
    def get_parameters(self):
        """
        Return the expected parameters for the tool as a dictionary.
        Derived classes must implement this method.

        :return: A dictionary describing the tool's parameters.
        """
        pass

    def handle_error(self, error: Exception):
        """
        Handle errors that occur during the tool's execution.

        :param error: The exception instance.
        :return: A standardized error message or response.
        """
        # Log the error (extend this with proper logging as needed)
        print(f"Error in tool '{self.name}': {error}")

        # Return a generic error response
        return {"error": str(error), "tool": self.name}


# Example derived tool
class ExampleTool(OpenAIToolBase):
    """
    Example implementation of a tool based on OpenAIToolBase.
    """

    def run(self, input_data: str):
        """
        Perform a mock operation.

        :param input_data: Some input to process.
        :return: Processed output.
        """
        try:
            # Example logic
            result = f"Processed: {input_data}"
            return {"result": result}
        except Exception as e:
            return self.handle_error(e)

    def get_parameters(self):
        """
        Define the expected parameters for this tool.

        :return: A dictionary describing parameters.
        """
        return {
            "type": "object",
            "properties": {
                "input_data": {
                    "type": "string",
                    "description": "The input data to process.",
                }
            },
            "required": ["input_data"],
        }


# Example usage
tool = ExampleTool(name="example_tool", description="A mock tool for demonstration.")
print(tool.to_json())
print(tool.run("Hello, OpenAI!"))
