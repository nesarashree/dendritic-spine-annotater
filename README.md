# Dendritic Spine Annotator

### Install Python
1. Download the latest [Python release](https://www.python.org/downloads/).
2. Follow the installation prompts.
3. Verify Python is installed by opening the **Mac Terminal** and running:
   ```bash
   python3 --version
   ```
### Set Up Visual Studio Code
1. [Download VS Code](https://code.visualstudio.com/) to your Downloads folder.  
2. Open the application.
3. Click the **Extensions** button in the left sidebar.
4. Search for **Python** and install the one published by **Microsoft**.
5. Open the **Command Palette** with:
   ```
   ⇧ Shift + ⌘ Command + P
   ```
6. Search for "Python: Select Interpreter"
7. Select the interpreter that matches the Python version you installed earlier.  

### Install Dependencies
In the **Mac Terminal**, install the required Python libraries:

```bash
pip install tifffile
pip install numpy
pip install pillow
pip install pandas
```
*(Other dependencies such as `tkinter`, `os`, and `math` should come pre-installed with Python.)*

### Run the Program
1. Quit and relaunch VS Code.  
2. Download the program file `label_dendritic_spines.py` from this repository.  
3. In VS Code, go to **File > Open** and open the `.py` file.  
4. Click the **Run** button (▶) in the top-right corner of VS Code.  
Your environment is ready, and you can now annotate dendritic spines. 🎉
