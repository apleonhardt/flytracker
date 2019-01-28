from modules import BruchpilotApplication
from time import sleep

if __name__ == "__main__":
    # Main entry point for application:

    app = BruchpilotApplication("./settings.yaml")
    app.start()
