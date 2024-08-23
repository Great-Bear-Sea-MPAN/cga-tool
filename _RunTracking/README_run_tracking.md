# CGA Run Tracking Instructions
This file provides guidance on how to capture the results of a script run.

# Instructions
* Run the CGA script with the necessary datasets.
* Once complete, add a new entry to the run tracking spreadsheet:
    * Navigate to _RunTracking > Tracking_PastRuns > CGA_Run_Tracking.xlsx.
    * Establish a new run ID based on the date you ran the script.
    * Add a new entry above the previous recorded runs.
    * Add all dataset references and notes on the run results.
* Copy the tabular inputs and logging file to the data folder:
    * Navigate to _RunTracking > Data_PastRuns.
    * Using the sample folder as a guide (_2024-01-01_SAMPLE), create a new folder named with your run ID (usually YYYY-MM-DD, but you may also wish to add an explanatory suffix, like YYYY-MM-DD_ScenarioP3). Add subfolders for inputs, outputs, and logging.
    * Add the tabular input files to /input.
    * Add the output files to /output.
    * Add the cga_script.log file to /logging.

## Spatial data
In general, the spatial datasets should be excluded from the data folder due to their large size. However, if you have a custom spatial dataset that should be preserved, feel free to customize the subfolders to include relevant datasets as needed.