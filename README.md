<h2> Automated Stock Screening and Trend Analysis :  </h2>
A Python-based toolkit designed for automated financial data retrieval, symbol management, and trend analysis for stock market data. <br> <br>    🚀 Features   
Automated Data Processing (data_dw.py, finder.py): Efficiently fetches and manages financial symbols and datasets.  
Trend Analysis (trend_liner.py): Computes trend lines, technical indicators, and price momentum.  
Core Execution Engine (mainv2.py): The primary, upgraded execution pipeline for running analysis workflows.  
Batch Automation (run_all.bat): Convenient Windows batch script to orchestrate and execute the full analysis pipeline seamlessly.  <br>

📁 Project Structure   <br>
├── finder.py         # Symbol and asset discovery module  <br>
├── data_dw.py        # Data downloader and warehouse handler  <br>
├── trend_liner.py    # Technical analysis and trend detection engine  <br>
├── mainv2.py         # Primary/Upgraded execution pipeline   <br>
├── run_all.bat       # Windows batch script for automated runs  <br>
├── input_symbols.txt # Configuration list of trading symbols  <br>
└── .gitignore        # Git ignore rules

⚙️ Installation & Prerequisites
Python 3.x installed on your system.
Required Python libraries:  pip install pandas numpy requests


🏃 UsageRunning via Batch Script (Windows) 
Execute run_all.bat from your command prompt or double-click it to run the complete pipeline: run_all.bat
Running Manually via PythonTo run the primary analysis pipeline using the active script: python mainv2.py

🛠️ ConfigurationModify input_symbols.txt to add or update the stock symbols and assets you want to track and analyze.

📄 License
This project is open-source and available for personal and educational use.
