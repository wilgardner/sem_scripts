# Hitachi SU7000 Field Emission SEM Scripts
A collection of scripts for automating scanning electron microscope (SEM) data acquisition. These are designed using the Python API for the Hitachi SU7000 Field Emission SEM. Note that camelCase is used to be consistent with the API style.

***

## autoMontage 
### Automated Montage Acquisition
This script automates the process of creating stage scan montages using the Hitachi SU7000 Field Emission Scanning Electron Microscope (SEM) through its Python API. It is designed to facilitate large area scans with precise control over imaging parameters and automatic adjustments for focus and astigmatism.

### Key Features:
- **Montage Creation**: Automatically generates montages based on specified start coordinates, total height, and width, with adjustable overlap between tiles to ensure seamless stitching.
- **Automatic Brightness and Contrast**: Option to automatically adjust brightness and contrast either for a single detector image or across all detectors, enhancing image quality.
- **Auto Focus with Recursive Adjustment**: Employs an advanced auto-focus mechanism that can recursively adjust focus if the initial autofocus fails to meet the specified threshold, thereby ensuring consistently sharp images across the montage.
- **Auto Astigmatism Correction**: Optionally corrects astigmatism automatically to improve image resolution and clarity.
- **Magnification Control**: Allows setting a specific magnification for the montage or utilising the current magnification setting of the microscope.
- **Flexible Image Capture**: Supports capturing either a single detector image or images from all detectors, according to the user's preference.
- **Safety Features**: Includes an option to automatically turn off the electron gun after acquisition, reducing wear on the microscope.

### How It Works:
- **Initialisation**: The script starts by gathering the current stage position and magnification, setting them as the starting point for the montage if not specified otherwise.
- **Tile Calculation**: It calculates the number of tiles needed to cover the specified area, taking into account the desired overlap and the effective tile dimensions derived from the set magnification.
- **Positioning and Imaging**: For each tile position, the script moves the stage accordingly, performs automatic brightness and contrast correction if enabled, and then captures images. If auto focus is enabled, it attempts to focus at each tile position, recursively adjusting the focus if necessary by moving a small offset and retrying, ensuring optimal focus is achieved.
- **Astigmatism Correction**: If enabled, automatically corrects astigmatism after focusing at each position.
- **File Management**: Captured images are saved with a base filename and numbered according to their position in the montage. Supports capturing and saving images from all detectors if selected.
- **Completion**: After capturing all required tiles, the script returns the stage to its initial position and optionally turns off the electron gun.

### Important Notes:
- Currently the script will only acquire montages in a zig-zag fashion, starting from the BOTTOM LEFT of the montage.
- The recursive auto focus will move small amounts in the positive X direction at each recursion (if the FOCUS_THRESHOLD is exceeded). Another option would be to use a random walk.
- The script does not do any stitching of the tiles into a final montage. This can be done using external image processing software.

***

