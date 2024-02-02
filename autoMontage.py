# Script for automating scanning electron microscopy (SEM) data acquisition
# using the Python API for Hitachi SU7000 Field Emission SEM.
# Features include montage creation, auto-focus with recursive adjustment,
# auto brightness and contrast, and more.

# Created in 2024 by Wil Gardner, Centre for Materials and Surface Science, La Trobe University

import shutil
from tkinter.tix import TCL_FILE_EVENTS
import os
from MfKeyMouse import *
from MfExtCont import *
from MfCommon import *

def Script():

    ##------------------ Editable section start ------------------##
    
    # Parameters (all units in NANOMETRES)

    # Montage parameters
    MONTAGE_START_COORDS = None #Start X and Y coordinates in nm - if None, use current position
    TOTAL_HEIGHT = 3300000 #Height of montage in nm
    TOTAL_WIDTH = 8000000 #Width of montage in nm
    TILE_OVERLAP = 0.2 #Fraction of overlap between adjacent tiles

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

    # Other settings
    HV_OFF_ON_END = True #Turn Gun off after acquisition
    
    # Folder paths
    TEMP_OUTPUT_PATH = r'path/to/temp/output/folder' #Path to TEMPORARY folder, where data is initially saved
    OUTPUT_PATH = r'path/to/output/folder' #Path to output folder
    FILENAME_BASE = 'filename' #Base filename

    ##------------------ Script start ------------------##

    # Get current coordinates
    r = EXT.GetStagePosition()
    startCoords = [r[2], r[3]]

    # Set start coordinates and magnification if not specified
    if MONTAGE_START_COORDS is None:
        r = EXT.GetStagePosition()
        montageStartCoords = [r[2], r[3]]
    else:
        montageStartCoords = MONTAGE_START_COORDS

    if MAG_VALUE is None:
        r = EXT.GetMagnification()
        magValue = r[3]
    else:
        magValue = MAG_VALUE

    # Set Magnification
    r = EXT.SetMagnification(Value=magValue)

    # Compute tile height and width from magnification
    tileHeight, tileWidth = computeTileSize(magValue=magValue)

    # Compute capture positions X/Y, with units in nanometres
    capturePositions = computeCapturePositions(
        startCoords=montageStartCoords,
        totalHeight=TOTAL_HEIGHT,
        totalWidth=TOTAL_WIDTH,
        tileHeight=tileHeight,
        tileWidth=tileWidth,
        tileOverlap=TILE_OVERLAP
    )

    # Set HV-ON
    r = EXT.SetHv(OnOff='ON')

    # Capture at all positions
    for i, [X, Y] in enumerate(capturePositions):
        
        # Move stage with coords (X and Y)
        r = EXT.RunStageMove(X=X, Y=Y)

        # ABCC
        if USE_ABC:
            r = EXT.RunAutoAbc(Mode=ABC_MODE, Bm=0)

        # AFC
        if USE_AUTO_FOCUS:
            #Set new magnficiation
            if magValue < AFC_MAG:
                r = EXT.SetMagnification(Value=AFC_MAG)
            
            recursiveAutofocus(tileWidth=tileWidth, focusThreshold=FOCUS_THRESHOLD, xStart=X, maxRecursions=MAX_AFC_RECURSIONS)
    
        # AST
        if USE_AUTO_ASTIGMA:
            r = EXT.RunAutoAsc()

        # Set Magnification
        r = EXT.SetMagnification(Value=magValue)

        # Capture
        r = EXT.RunCapture(
            Type=CAPTURE_TYPE, 
            Dir=TEMP_OUTPUT_PATH, 
            File='tempfile'
        )

        ## Rename capture files (bmp file and txt file)
        if CAPTURE_TYPE == 0:
            # Iterate filename
            filename = f'{FILENAME_BASE}_{i}'
            shutil.move(
                os.path.join(TEMP_OUTPUT_PATH, "tempfile.bmp"), 
                os.path.join(OUTPUT_PATH, f"{filename}.bmp")
            )
            shutil.move(
                os.path.join(TEMP_OUTPUT_PATH, "tempfile.txt"), 
                os.path.join(OUTPUT_PATH, f"{filename}.txt")
            )
        else:
            # Save all detector images as separate files
            for j in range(6): #TODO only loop through ACTIVE detectors
                f_path = os.path.join(TEMP_OUTPUT_PATH, f'tempfile_0{j}')
                if os.path.exists(f'{f_path}.bmp'):
                    # Iterate filename with scan number and detector number
                    filename = f'{FILENAME_BASE}_d{j}_{i}'
                    shutil.move(f'{f_path}.bmp', os.path.join(OUTPUT_PATH, f'{filename}.bmp'))
                    shutil.move(f'{f_path}.txt', os.path.join(OUTPUT_PATH, f'{filename}.txt'))
       
        # Run
        state = 0                              # 0:Run, 1:Freeze, 2:Freeze(forced)
        r = EXT.RunScan(ScanState = state)

    # Return to start position
    r = EXT.RunStageMove(X=startCoords[0], Y=startCoords[1])

    # HV-OFF
    if HV_OFF_ON_END:
        r = EXT.SetHv(OnOff='OFF')

    Exit()
    return

#Helper functions
def computeTileSize(magValue):
    """Computes the tile height and width (in nm) based on magnification"""

    photoSize = EXT.GetPhotoSize();  # Command to SU7000 to grab the current frame size (seems to be an arbitrary number)
    #Calculate actual image height/width (in nanometres)
    tileWidth = (127000 * photoSize[3] / magValue); 
    tileHeight = (95250 * photoSize[3] / magValue)

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
    
    return capturePositions

def recursiveAutofocus(tileWidth, focusThreshold, xStart, offset=0, count=0):
    """A recursive function to apply autofocus at an offset location if unsuccesful at current location"""

    if count > 5:
        return

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

    if abs(newWorkingDistance - oldWorkingDistance) > focusThreshold:
                
        #Restore old focus
        r = EXT.SetFocus(Coarse=oldFocus)

        recursiveAutofocus(tileWidth, focusThreshold, xNew, offset=int(0.1*tileWidth), count = count + 1)

        #Restore position
        r = EXT.RunStageMove(X=xStart)
   