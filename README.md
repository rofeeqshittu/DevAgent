# DevAgent: Autonomous Telegram Coding Assistant

DevAgent is a powerful, autonomous coding assistant integrated directly into Telegram. Powered by the Google Antigravity SDK, it acts as a senior developer living directly on your VPS, allowing you to execute terminal commands, edit codebases, push to GitHub, and debug software entirely from your phone.

## Features

- **Full Terminal Access**: Execute bash commands via the Telegram interface.
- **Intelligent Code Editing**: The agent can read, write, and replace file contents efficiently.
- **Strict Safety Handcuffs**: Destructive commands (like `rm`, `git push`, or modifying files) are intercepted. The bot will send you a prompt with `[ ✅ Approve ]` and `[ ❌ Deny ]` buttons on Telegram, ensuring the agent never breaks your server.
- **Multimodal**: Native support for screenshots. Send a picture of a UI bug, and the agent can see it, find the CSS/HTML, and fix it.
- **Isolated State**: Maintains its own `agent_state` directory, seamlessly persisting conversation context across messages.

## Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:rofeeqshittu/DevAgent.git
   cd DevAgent
   ```
2. Create and activate the virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up the `.env` file:
   ```bash
   TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
   GEMINI_API_KEY="your_gemini_api_key"
   ```

## Running the Bot

Run the bot as a background process using `screen`:
```bash
screen -dmS devagent python3 /opt/DevAgent/bot.py
```

## Usage

1. Open Telegram and start a chat with your new bot.
2. Send a command like:
   * *"Create a new React component for a login screen in `/opt/my-app`"*
   * *"Check `git status` in the StreamVault folder and push the changes."*
   * *(Send an image)* *"Fix the alignment of this button in the CSS file."*
3. When the agent attempts to run a modifying tool, it will pause and prompt you for approval. Click **Approve** to authorize the action.

## Core Rules (`GEMINI.md` / `CLAUDE.md`)
This project strictly adheres to the rules defined in `GEMINI.md`:
- **Boil the Ocean**: Ensure total error handling and robustness.
- **Search Before Building**: Verify documentation and paths before executing.
- **Safety First**: Destructive operations must always be trapped and approved.
