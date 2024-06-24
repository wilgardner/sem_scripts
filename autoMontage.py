# Script for automating scanning electron microscopy (SEM) data acquisition
# using the Python API for Hitachi SU7000 Field Emission SEM.
# Features include montage creation, auto-focus with recursive adjustment,
# auto brightness and contrast, and more.

# Created in 2024 by Wil Gardner, Centre for Materials and Surface Science, La Trobe University

import shutil
import os

from MfKeyMouse import *
from MfExtCont import *
from MfCommon import *

##------------------ PARAMETERS START ------------------##

# Parameters (all units in MILLIMETRES)

# Montage parameters
MONTAGE_START_COORDS = None #Start X and Y coordinates in nm - if None, use current position
TOTAL_HEIGHT = 6.4 #Height of montage in mm
TOTAL_WIDTH = 9 #Width of montage in mm
TILE_OVERLAP = 0.2 #Fraction of overlap between adjacent tiles
SEC_PER_TILE = 50 #Approximate seconds spent on each tile (ONLY USED TO APPROXIMATE SCAN TIME)

# Scan settings
MAG_VALUE = None #Magnification - if None, use current magnification
USE_ABC = False #Whether to use auto brightness and contrast correction for each tile
ABC_MODE = 1 #To which detector image(s) should ABC be applied (0:Single, 1:All)
CAPTURE_TYPE = 1 #Which detector image(s) to capture (0:Single, 1:All)
USE_AUTO_FOCUS = True #Whether to use auto focus
FOCUS_THRESHOLD = 100 #Working distance change threshold (microns) when auto focusing
AFC_MAG = 5000 #Magnification for autofocus
MAX_AFC_RECURSIONS = 5 #Maximum number of recursions/attempts when trying to autofocus
USE_AUTO_ASTIGMA = False #Whether to use auto astigmatism
HV_OFF_ON_END = True #Turn Gun off after acquisition

# Output settings
TEMP_OUTPUT_DIR = r'path/to/temp/output/folder' #Path to TEMPORARY folder, where data is initially saved
OUTPUT_DIR = r'path/to/output/folder' #Path to output folder
FILENAME_BASE = 'filename' #Base filename, on which to increment the individual filenames

# Path to mask image if using - set to None if not using
MASK_PATH = None

##-------------------- SCRIPT START --------------------##

if MASK_PATH is not None:
    #Import required libraries
    import numpy as np
    from PIL import Image

#Path to log file and log function (logs all print statements)
LOG_FILE_PATH = os.path.join(OUTPUT_DIR, 'script_log.txt')
def log_message(message):
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(message + '\n')

def Script():
    # Get current coordinates
    r = EXT.GetStagePosition()
    startCoords = [r[2], r[3]]
    log_message(f'Current coordinates: {startCoords}')

    # Set start coordinates and magnification if not specified
    if MONTAGE_START_COORDS is None:
        r = EXT.GetStagePosition()
        montageStartCoords = [r[2], r[3]]
    else:
        montageStartCoords = MONTAGE_START_COORDS
    log_message(f'Montage start coordinates: {montageStartCoords}')

    if MAG_VALUE is None:
        r = EXT.GetMagnification()
        magValue = r[3]
    else:
        magValue = MAG_VALUE
    log_message(f'Magnification value: {magValue}')

    # Set Magnification
    r = EXT.SetMagnification(Value=magValue)

    # Compute tile height and width from magnification
    tileHeight, tileWidth = computeTileSize(magValue=magValue)
    log_message(f'Tile height: {tileHeight}, Tile width: {tileWidth}')

    # Compute capture positions X/Y, with units in nanometres
    capturePositions, numTilesHeight, numTilesWidth = computeCapturePositions(
        startCoords=montageStartCoords,
        totalHeight=TOTAL_HEIGHT,
        totalWidth=TOTAL_WIDTH,
        tileHeight=tileHeight,
        tileWidth=tileWidth,
        tileOverlap=TILE_OVERLAP
    )

    # Load mask if path is not None
    if MASK_PATH is not None:
        # Load image, resize to match tiles, and binarize
        binary_image = rgbToTileBinary(MASK_PATH, (numTilesWidth, numTilesHeight))
    
        # Flatten to match the zig-zag capture
        mask = zigzagFlatten(binary_image)

        if len(mask) != len(capturePositions):
            log_message('ERROR! Mask length not equal to capturePositions length.')
            Exit()
            return
        log_message(f'Approximate time to complete montage (hr): {SEC_PER_TILE*np.count_nonzero(mask)/3600}')
    else:
        log_message(f'Approximate time to complete montage (hr): {SEC_PER_TILE*len(capturePositions)}')
        
    # Set HV-ON
    r = EXT.SetHv(OnOff='ON')

    # Capture at all positions
    for i, [X, Y] in enumerate(capturePositions):
        
        if MASK_PATH is not None and not mask[i]:
            continue
        
        # Move stage with coords (X and Y)
        r = EXT.RunStageMove(X=X, Y=Y)
        log_message(f'Moved stage to position {i}: X={X}, Y={Y}')

        # ABCC
        if USE_ABC:
            r = EXT.RunAutoAbc(Mode=ABC_MODE, Bm=0)
            log_message('Auto brightness and contrast correction applied.')

        # AFC
        if USE_AUTO_FOCUS:
            #Set new magnficiation
            if magValue < AFC_MAG:
                r = EXT.SetMagnification(Value=AFC_MAG)
            
            #Recursively focus
            focusSuccessful = recursiveAutofocus(tileWidth=tileWidth, focusThreshold=FOCUS_THRESHOLD, xStart=X, maxRecursions=MAX_AFC_RECURSIONS)
            if focusSuccessful:
                log_message('Recursive auto focus applied successfully.')
            else:
                log_message('Recursive auto focus failed. Using previous tile focus.')
    
        # AST
        if USE_AUTO_ASTIGMA:
            r = EXT.RunAutoAsc()
            log_message('Auto astigmatism correction applied.')

        # Set Magnification
        r = EXT.SetMagnification(Value=magValue)

        # Capture
        r = EXT.RunCapture(
            Type=CAPTURE_TYPE, 
            Dir=TEMP_OUTPUT_DIR, 
            File='tempfile'
        )
        log_message(f'Captured image at position {i}.')

        ## Rename capture files (bmp file and txt file)
        if CAPTURE_TYPE == 0:
            # Iterate filename
            filename = f'{FILENAME_BASE}_{i}'
            shutil.move(
                os.path.join(TEMP_OUTPUT_DIR, "tempfile.bmp"), 
                os.path.join(OUTPUT_DIR, f"{filename}.bmp")
            )
            shutil.move(
                os.path.join(TEMP_OUTPUT_DIR, "tempfile.txt"), 
                os.path.join(OUTPUT_DIR, f"{filename}.txt")
            )
        else:
            # Save all detector images as separate files
            for j in range(6): #TODO only loop through ACTIVE detectors
                f_path = os.path.join(TEMP_OUTPUT_DIR, f'tempfile_0{j}')
                if os.path.exists(f'{f_path}.bmp'):
                    # Iterate filename with scan number and detector number
                    filename = f'{FILENAME_BASE}_d{j}_{i}'
                    shutil.move(f'{f_path}.bmp', os.path.join(OUTPUT_DIR, f'{filename}.bmp'))
                    shutil.move(f'{f_path}.txt', os.path.join(OUTPUT_DIR, f'{filename}.txt'))
        log_message(f'Files saved for position {i}.')
        # Run
        state = 0                              # 0:Run, 1:Freeze, 2:Freeze(forced)
        r = EXT.RunScan(ScanState = state)

    # Return to start position
    r = EXT.RunStageMove(X=startCoords[0], Y=startCoords[1])
    log_message('Returned to start position.')

    # HV-OFF
    if HV_OFF_ON_END:
        r = EXT.SetHv(OnOff='OFF')
        log_message('HV set to OFF.')

    Exit()
    return

#Helper functions
def computeTileSize(magValue):
    """Computes the tile height and width (in nm) based on magnification"""

    photoSize = EXT.GetPhotoSize();  # Command to SU7000 to grab the current frame size (seems to be an arbitrary number)
    #Calculate actual image height/width (in millimetres)
    tileWidth = (0.127 * photoSize[3] / magValue); 
    tileHeight = (0.09525 * photoSize[3] / magValue)

    return tileHeight, tileWidth

def computeCapturePositions(startCoords, totalHeight, totalWidth, tileHeight, tileWidth, tileOverlap):
    """Computes the capture positions (in nm) in the stage scan based on settings"""

    xStart, yStart = startCoords

    # Calculate effective tile dimensions considering overlap
    effectiveTileHeight = int(tileHeight * (1 - tileOverlap))
    effectiveTileWidth = int(tileWidth * (1 - tileOverlap))
 
    # Adjust totalHeight and totalWidth to be multiples of effectiveTileHeight and effectiveTileWidth
    totalHeight -= totalHeight % effectiveTileHeight
    totalWidth -= totalWidth % effectiveTileWidth  
    
    # Convert to nm
    totalHeight *= 1E6
    totalWidth *= 1E6
    effectiveTileHeight *= 1E6
    effectiveTileWidth *= 1E6 

    # Calculate the number of tiles in each dimension
    numTilesHeight = int(totalHeight / effectiveTileHeight)
    numTilesWidth = int(totalWidth / effectiveTileWidth)

    capturePositions = []

    # Generate positions in a zig-zag pattern
    for row in range(numTilesHeight):
        if row % 2 == 0:  # Moving right
            for col in range(numTilesWidth):
                x = xStart + col * effectiveTileWidth
                y = yStart + row * effectiveTileHeight
                capturePositions.append([int(x), int(y)])
        else:  # Moving left
            for col in range(numTilesWidth - 1, -1, -1):
                x = xStart + col * effectiveTileWidth
                y = yStart + row * effectiveTileHeight
                capturePositions.append([int(x), int(y)])
    
    return capturePositions, numTilesHeight, numTilesWidth

def recursiveAutofocus(tileWidth, focusThreshold, xStart, offset=0, maxRecursions=5):
    """A recursive function to apply autofocus at an offset location if unsuccesful at current location"""

    if maxRecursions <= 0:
        #Focus unsuccessful so return False
        return False

    xNew = xStart + offset

    if offset > 0:
        
        r = EXT.RunStageMove(X=xNew)

    #Get current focus and working distance
    r = EXT.GetFocus()
    oldFocus = r[2]
    r = EXT.GetWorkingDistance()
    oldWorkingDistance = r[2]
    
    #Run autofocus
    r = EXT.RunAutoAfc()

    #Get new working distance
    r = EXT.GetWorkingDistance()
    newWorkingDistance = r[2]

    focusSuccessful = True
    if abs(newWorkingDistance - oldWorkingDistance) > focusThreshold:
                
        #Restore old focus
        r = EXT.SetFocus(Coarse=oldFocus)

        focusSuccessful = recursiveAutofocus(tileWidth, focusThreshold, xNew, offset=int(0.1*tileWidth), maxRecursions=maxRecursions-1)

        #Restore position
        r = EXT.RunStageMove(X=xStart)
    return focusSuccessful
    
def rgbToTileBinary(image_path, resize_shape=None):
    # Load image using PIL
    image_pil = Image.open(image_path)
    
    # Resize image if requested
    if resize_shape is not None:
        image_pil = image_pil.resize(resize_shape, Image.BICUBIC)
    
    # Convert image to grayscale
    grayscale_image = image_pil.convert('L')
    
    # Convert grayscale image to numpy array
    grayscale_array = np.array(grayscale_image) / 255.0  # Normalize to range [0, 1]

    # Apply thresholding
    binary_image = grayscale_array >= 0.5
    binary_image = binary_image.astype('int')

    return binary_image

def zigzagFlatten(array_2d):
    # Flip the entire array vertically
    array_2d = np.flip(array_2d, axis=0)

    # Flip every second row starting from the second from bottom
    array_2d[1::2] = np.flip(array_2d[1::2], axis=1)
    
    # Flatten the array
    return np.reshape(array_2d, (1, -1))