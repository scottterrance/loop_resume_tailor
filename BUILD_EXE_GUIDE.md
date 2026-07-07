# How to Build Loop Resume Tailor as a Windows `.exe`

This guide explains how to package your Python Flask backend and React frontend into a single, standalone Windows executable (`.exe`) file. This allows users to run the app without installing Python, Node.js, or any dependencies.

## Prerequisites

Before you begin, ensure you have the following installed on your Windows machine:
1. **Python 3.10+** (Make sure "Add Python to PATH" was checked during installation)
2. **Node.js 18+** (For building the React frontend)
3. **Git** (To clone your repository)

## Step 1: Build the React Frontend

First, we need to compile the React frontend into static HTML/CSS/JS files that the Python backend can serve.

1. Open a terminal (Command Prompt or PowerShell) and navigate to your project directory:
   ```cmd
   cd path\to\loop_resume_tailor
   ```

2. Navigate to the frontend directory (assuming it's in a folder like `frontend` or `client`):
   ```cmd
   cd frontend
   ```

3. Install the Node.js dependencies:
   ```cmd
   npm install
   ```

4. Build the production version of the frontend:
   ```cmd
   npm run build
   ```

5. Copy the contents of the generated `build` (or `dist`) folder into your Flask backend's `static` and `templates` folders. 
   - Move `index.html` to the Flask `templates` folder.
   - Move the `static/js` and `static/css` folders to the Flask `static` folder.

## Step 2: Prepare the Python Backend

We will use **PyInstaller** to package the Python code.

1. Navigate back to the root of your project:
   ```cmd
   cd ..
   ```

2. Create a virtual environment and activate it:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install your project's dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

4. Install PyInstaller:
   ```cmd
   pip install pyinstaller
   ```

## Step 3: Create the PyInstaller Configuration

PyInstaller needs to know to include your `static` and `templates` folders, as well as any other data files (like the `outputs` folder).

1. Run the initial PyInstaller command to generate a `.spec` file:
   ```cmd
   pyinstaller --name "LoopResumeTailor" --noconfirm app.py
   ```
   *(Note: Replace `app.py` with your main entry point file if it's named differently).*

2. Open the generated `LoopResumeTailor.spec` file in a text editor.

3. Modify the `datas` array to include your static files, templates, and the outputs directory. It should look something like this:
   ```python
   datas=[
       ('templates', 'templates'),
       ('static', 'static'),
       ('outputs', 'outputs'),
       ('.env', '.') # If you use a .env file for API keys
   ],
   ```

## Step 4: Build the Executable

1. Run PyInstaller using the modified `.spec` file:
   ```cmd
   pyinstaller LoopResumeTailor.spec
   ```

2. Wait for the process to complete. This may take a few minutes as it bundles Python and all dependencies.

## Step 5: Locate and Run Your `.exe`

1. Once the build is finished, navigate to the newly created `dist` folder:
   ```cmd
   cd dist\LoopResumeTailor
   ```

2. Inside, you will find `LoopResumeTailor.exe`. 

3. Double-click `LoopResumeTailor.exe` to run your application. A terminal window will open showing the Flask server starting up, and you can access the app in your browser at `http://localhost:5000` (or whichever port your app uses).

### Important Notes for Distribution
- **API Keys:** If your app relies on an `.env` file for the OpenAI API key, make sure to distribute the `.env` file alongside the `.exe`, or build a UI feature that allows the user to input their API key directly into the app.
- **File Paths:** Ensure your Python code uses relative paths (e.g., `os.path.join(os.path.dirname(__file__), 'outputs')`) rather than hardcoded absolute paths, so it works on any computer.
- **Single File Build:** If you want exactly *one* file instead of a folder, you can add the `--onefile` flag to your PyInstaller command, but note that this makes the app start up much slower because it has to extract itself to a temporary directory every time it runs.
