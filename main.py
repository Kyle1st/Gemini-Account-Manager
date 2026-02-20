"""
Gemini Account Manager
Entry point for the application.
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from ui_main import MainApplication


def main():
    app = MainApplication()
    app.mainloop()


if __name__ == "__main__":
    main()
