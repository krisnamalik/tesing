# Ver_5_K_180124
# Resolve naming file for custom script
# Resolve nodata value for custom (+) coefficient 

# Ver_6_K_210124
# Resolve nodata conflict

# Ver_7_K_230124
# Simplify some conditional
# Error warning

# Ver_8_E_230125
# Adding Error Checking
# Adding Function to open output folder (check if it's on windows or linux)
# Removing CheckBackslash function, not used

# Ver_9_E_240125
# 

import geopandas as gpd
import glob
import numpy as np
import os
import subprocess
import sys
import shutil
import tarfile
import tkinter as tk
import unpackqa
from datetime import datetime
from rasterio.mask import mask
from tkinter import filedialog
from tkinter import *
from threading import *
import rasterio
from tkinter.messagebox import showinfo, showerror

# GUI Window
window=tk.Tk()
window.title("BRIN - GHG Emission Calculator")
window.geometry("500x250")

# User Inputs Def
var_inputDir = tk.StringVar()
var_outputDir = tk.StringVar()
var_shpPath = tk.StringVar()
var_index = tk.StringVar()
var_index.set("NDVI")
index_options = [
    "NDVI",
    "EVI2"
]
var_products = tk.StringVar()
var_products.set("CH4")
products_options =[
    "CH4",
    "N20",
    "C02"
]
var_checkCustom = tk.IntVar()
var_intercept = tk.StringVar()
var_coefficient = tk.StringVar()

def inputDir():
    path_dir=filedialog.askdirectory()
    var_inputDir.set(path_dir)

def outputDir():
    path=filedialog.askdirectory()
    var_outputDir.set(path)

def shpFile():
    path=filedialog.askopenfilename(
        title="Select a Shapefile",
        filetypes=[("Shapefiles", "*.shp")]
    )
    var_shpPath.set(path)

def checkCustom():
    if var_checkCustom.get() == 1:
        InterceptEntry["state"] = "normal"
        coefficientEntry["state"] = "normal"
    else:
        InterceptEntry["state"] = "disabled"
        coefficientEntry["state"] = "disabled"

def open_file_or_dir(output_dir):
    if sys.platform == "linux":
        subprocess.run(["xdg-open", output_dir], check=True)
    elif sys.platform == "win32":
        os.startfile(output_dir)
    elif sys.platform == "darwin":  # macOS
        subprocess.run(["open", output_dir], check=True)
    else:
        print("Unsupported OS")

def crop(img, shp):
    if img.crs != shp.crs:
        shp = shp.to_crs(img.crs)
        img_crop, trans = mask(img, shp.geometry, crop=True)
    else:
        img_crop, trans = mask(img, shp.geometry, crop=True)
        
    clean_crop = np.select([img_crop[0] == 0], [np.nan], img_crop[0])
    return clean_crop

def cloud_masking(qa, b4, b5, shp):
    b4 = crop(b4, shp)
    b5 = crop(b5, shp)

    flag = unpackqa.unpack_to_array(qa, 
                                product='LANDSAT_8_C2_L2_QAPixel', 
                                flags=['Cloud','Fill','Dilated_Cloud','Cirrus','Cloud_Shadow'])
    cloud_mask = np.select([flag[:,:,0] == 0, flag[:,:,0] == 1], [1, np.nan], flag[:,:,0])
    fill_mask = np.select([flag[:,:,1] == 0, flag[:,:,1] == 1], [1, np.nan], flag[:,:,1])
    dilated_mask = np.select([flag[:,:,2] == 0, flag[:,:,2] == 1], [1, np.nan], flag[:,:,2])
    shadow_mask = np.select([flag[:,:,3] == 0, flag[:,:,3] == 1], [1, np.nan], flag[:,:,3])
    cirrus_mask = np.select([flag[:,:,4] == 0, flag[:,:,4] == 1], [1, np.nan], flag[:,:,4])
    
    b4_mask = b4*cloud_mask*fill_mask*dilated_mask*shadow_mask*cirrus_mask
    b5_mask = b5*cloud_mask*fill_mask*dilated_mask*shadow_mask*cirrus_mask

    b4_scale = (b4_mask * 0.0000275) + -0.2
    b5_scale = (b5_mask * 0.0000275) + -0.2

    return b4_scale, b5_scale

def evi2_calculation(b4, b5, intercept, coefficient):
    if intercept is None:
        intercept = 536.72
    if coefficient is None:
        coefficient = - 156.54

    evi2 = 2.5 * ((b5 - b4) / (b5 + 2.4 * b4 + 1))
    methane = intercept * evi2 + coefficient
    methane = np.where(methane < 0, 0, methane)
    return methane

def ndvi_calculation(b4, b5,intercept, coefficient):
    if intercept is None:
        intercept = 321.99
    if coefficient is None:
        coefficient = - 158.12
        
    ndvi = (b5 - b4) / (b5 + b4)
    methane = intercept * ndvi + coefficient
    methane = np.where(methane < 0, 0, methane)
    return methane

def check_custom(custom):
    if custom == 1:
        if var_intercept.get().strip():
            intercept = float(var_intercept.get())
        else:
            intercept = None
        if var_coefficient.get().strip():
            coefficient = float(var_coefficient.get())
        else:
            coefficient = None
        prefix = 'custom_'
    else:
        intercept = None 
        coefficient = None
        prefix = "" 

    return intercept, coefficient, prefix

def on_product_change(*args):
    selected_product = var_products.get()
    if selected_product == "CH4":
        checkboxButton["state"] = "normal"
    else:      
        var_checkCustom.set(1)
        checkboxButton["state"] = "disabled"
        InterceptEntry["state"] = "normal"
        coefficientEntry["state"] = "normal"

def Submit():
    errors = []

    input_dir = var_inputDir.get()
    output_dir = var_outputDir.get()
    shp_path = var_shpPath.get()
    product = var_products.get()
    custom = var_checkCustom.get()
    intercept = var_intercept.get()
    coefficient = var_coefficient.get()

    if not input_dir or not os.path.isdir(input_dir):
        errors.append("Input Directory cannot be empty and must be a valid path.")

    if not output_dir or not os.path.isdir(output_dir):
        errors.append("Output Directory cannot be empty and must be a valid path.")

    if not shp_path.endswith(".shp"):
        errors.append("Shapefile path must be a valid .shp file.")

    if custom == 1:
        try:
            float(intercept)  # Must be convertible to float
        except ValueError:
            errors.append("Intercept cannot be empty and must be a valid number.")
        try:
            float(coefficient)  # Must be convertible to float
        except ValueError:
            errors.append("Coefficient cannot be empty and must be a valid number.")

    # Check if there are any errors
    if errors:
        showerror("Input Validation Errors", "\n".join(errors))
        return

    # If all validations pass, start the execution
    t1 = Thread(target=Execute)
    t1.start()

def Execute():
    start_time = datetime.now()
    SubmitLabel.place(x=0, y=200, anchor=NW)
    SubmitButton["state"] = "disabled"

    bands = ["B4", "B5", "QA_PIXEL"]
    satellite_name = "Landsat-8"
    input_dir = var_inputDir.get()
    output_dir = var_outputDir.get()
    shp_path = var_shpPath.get()
    index = var_index.get()
    products = var_products.get()
    custom = var_checkCustom.get()
    intercept = var_intercept.get()
    coefficient = var_coefficient.get()

    tmp_dir = os.path.join(os.path.dirname(output_dir),"tmp",satellite_name)
    os.makedirs(tmp_dir, exist_ok=True)

    shp = gpd.read_file(shp_path)
    files = glob.glob(os.path.join(input_dir, "*.tar"))

    for file in files:
        list_dir = []
        folder_name = os.path.basename(file).split(".")[0]
        extraction_dir = os.path.join(tmp_dir, folder_name)
        print(f"Processing: {file}")
        with tarfile.open(file, "r") as tar:
            for member in tar.getmembers():
                if any(band in member.name for band in bands):
                    tar.extract(member, path=extraction_dir)
                    print(f"Extracted: {member.name}")
                    
        for i in range(len(os.listdir(extraction_dir))):
            list_dir.append(os.listdir(extraction_dir)[i])
        
        s_listdir = sorted(list_dir)
        qab = rasterio.open(os.path.join(extraction_dir,s_listdir[0]))
        b4 = rasterio.open(os.path.join(extraction_dir,s_listdir[1]))
        b5 = rasterio.open(os.path.join(extraction_dir,s_listdir[2]))

        if shp.crs != qab.crs:
            print(f"Reprojecting shp from {shp.crs} to {qab.crs}")
            shp = shp.to_crs(qab.crs)
            qa_crop, trans = mask(qab, shp.geometry, crop=True)
        else:
            qa_crop, trans = mask(qab, shp.geometry, crop=True)
        
        band4, band5 = cloud_masking(qa_crop[0], b4, b5, shp)

        filedir = os.path.join(output_dir,folder_name)
        os.makedirs(filedir, exist_ok=True)

        if index == "EVI2":
            intercept, coefficient, prefix = check_custom(custom)
            methane_data = evi2_calculation(band4, band5, intercept, coefficient)
            filename_output = os.path.join(filedir, f"{prefix}{products}_{index}_{folder_name}.TIF")

        elif index == "NDVI":
            intercept, coefficient, prefix = check_custom(custom)
            methane_data = ndvi_calculation(band4, band5, intercept, coefficient)
            filename_output = os.path.join(filedir, f"{prefix}{products}_{index}_{folder_name}.TIF")

        else:
            raise ValueError(f"Unsupported index type: {index}")

        # Write the output to a GeoTIFF
        with rasterio.open(
            filename_output,
            mode="w",
            driver="GTiff",
            height=methane_data.shape[0],
            width=methane_data.shape[1],
            count=1,
            dtype=methane_data.dtype,
            crs=qab.crs,
            transform=trans,
        ) as dataset:
            dataset.write(methane_data, 1)

    b4.close()
    b5.close()
    qab.close()
    shutil.rmtree(tmp_dir)
    os.rmdir(os.path.dirname(tmp_dir))

    end_time = datetime.now()
    elapsed_time = end_time - start_time
    elapsed_time_str = str(elapsed_time).split('.')[0]
    
    response = showinfo(
        "Processing Complete",
        f"All data processing has been completed successfully!\nElapsed time: {elapsed_time_str}\n\n",
        icon='info'
    )
    
    if response == 'ok':
        open_file_or_dir(output_dir)
        window.quit()
    
# Input
InputLabel = tk.Label(window, text = 'Satellite Data Directory', font=('calibre',10, 'bold'))
InputLabel.place(x=0,y=0,anchor=NW)

InputEntry = tk.Entry(window,textvariable = var_inputDir, font=('calibre',10,'normal'))
InputEntry.place(x=180,y=0, width=190)

InputButton = tk.Button(window, text='Select Dir', command=inputDir)
InputButton.place(x=375,y=0,width=100,height=25)

# Output
OutputLabel = tk.Label(window, text = 'Raster Output Directory', font=('calibre',10, 'bold'))
OutputLabel.place(x=0,y=25,anchor=NW)

OutputEntry = tk.Entry(window, textvariable = var_outputDir, font = ('calibre',10,'normal'))
OutputEntry.place(x=180,y=25,width=190)

OutputButton = tk.Button(window, text='Select Dir', command=outputDir)
OutputButton.place(x=375,y=25,width=100, height=25)

# SHP file
SHPLabel = tk.Label(window, text = 'SHP File', font=('calibre',10, 'bold'))
SHPLabel.place(x=0,y=50,anchor=NW)

SHPEntry = tk.Entry(window, textvariable = var_shpPath, font = ('calibre',10,'normal'))
SHPEntry.place(x=180,y=50,width=190)

SHPButton = tk.Button(window, text='Select SHP', command=shpFile)
SHPButton.place(x=375,y=50, width=100, height=25)

# Index Options
IndexLabel = tk.Label(window, text = 'Products Options', font=('calibre',10, 'bold'))
IndexLabel.place(x=0,y=75,anchor=NW)
IndexButton = OptionMenu( window , var_index , *index_options ) 
IndexButton.place(x=250,y=75)

ProductsButton = OptionMenu( window , var_products , *products_options, command=lambda _: on_product_change())
ProductsButton.place(x=177,y=75)

# Checkbox
checkboxButton = Checkbutton( 
    window,
    text="Custom variables ?",
    font=('calibre',10, 'bold'),
    variable=var_checkCustom,
    onvalue=1,
    offvalue=0,
    command=checkCustom) 
checkboxButton.place(x=0,y=100)

# Custom Variables
InterceptLabel = tk.Label(window, text='Intercept', font=('calibre', 10, 'bold'))
InterceptLabel.place(x=0, y=125)
InterceptEntry = tk.Entry(window, textvariable=var_intercept, font=('calibre', 10, 'normal'), state='disabled')
InterceptEntry.place(x=180, y=125, width=190)

CoefficientLabel = tk.Label(window, text='Coefficient', font=('calibre', 10, 'bold'))
CoefficientLabel.place(x=0, y=150)
coefficientEntry = tk.Entry(window, textvariable=var_coefficient, font=('calibre', 10, 'normal'), state='disabled')
coefficientEntry.place(x=180, y=150, width=190)

# Submit
SubmitLabel = tk.Label(window, text = 'Data is being processed.', font=('calibre',10, 'bold'))

SubmitButton = tk.Button(window,text = 'Submit', command=Submit)
SubmitButton.place(x=177,y=195,width=80)

CRLabel = tk.Label(window, text = '© 2025 PRGI - BRIN v1.0', font=('calibre',11,'bold'), fg="RED")
CRLabel.place(x=273,y=225,anchor=SW)

SubmitLabel = tk.Label(window, text = 'Data is being processed.', font=('calibre',10, 'bold'))
window.mainloop()