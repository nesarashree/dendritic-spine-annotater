# Dendritic Spine Annotator

## 1. Install Python
1. Download the latest [Python release](https://www.python.org/downloads/).
2. Follow the installation prompts.
3. Verify Python is installed by opening the **Mac Terminal** and running:
   ```bash
   python3 --version
   ```
   You should see an output similar to:
   ```
   Python 3.x.x
   ```
   
## 2. Install Visual Studio Code
1. [Download VS Code](https://code.visualstudio.com/) and install it in your **Downloads** folder.  
2. Open the application.  

## 3. Install Python Extension in VS Code
1. Click the **Extensions** button in the left sidebar.  
2. Search for **Python** and install the one published by **Microsoft**.  

## 4. Select Python Interpreter
1. Open the **Command Palette** with:
   ```
   ⇧ Shift + ⌘ Command + P
   ```
2. Type **Python: Select Interpreter**.  
3. Select the interpreter that matches the Python version you installed earlier.  

## 5. Install Dependencies
In the **Mac Terminal**, install the required Python libraries:

```bash
pip install tifffile
pip install numpy
pip install pillow
pip install pandas
```
*(Other dependencies such as `tkinter`, `os`, and `math` come pre-installed with Python.)*

## 6. Launch the Program
1. Quit and relaunch VS Code.  
2. Download the program file `label_dendritic_spines.py` from this repository.  
3. In VS Code, go to **File > Open** and open the `.py` file.  
4. Click the **Run** button (▶) in the top-right corner of VS Code.  
Your environment is ready, and you can now annotate dendritic spines. 🎉
