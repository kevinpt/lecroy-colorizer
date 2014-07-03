=====================
LeCroy 93xx colorizer
=====================

Version: 1.0.1

LeCroy Colorizer is a command line utility to add color to the black and white
images produced by the screen capture on the LeCroy 93xx series oscilloscopes.
It should run without issue on all platforms that support Python and PIL.

Dependencies
------------
* Python 2.6 or newer. Not tested under Python 3 due to lack of PIL support
* `Python Imaging Library (PIL) <http://www.pythonware.com/products/pil>`_

Features
--------
* Colorize all portions of a 93xx series screen capture
* Automatically detects grid layout
* Provides user customizable colors
* Supports a wide variety of input and output image formats

Installation
------------
For all platforms, installation via setup.py is provided. This uses the
Distribute fork of setuptools and will install Distribute if it is not already
present. After extracting the compressed archive, run the following command:

``> python setup.py install``

This will install the lecroy-colorizer distribution (and PIL if necessary) into
your Python's site-packages and create an executable link to the colorize_lecroy
script.

The LeCroy colorizer has been tested on Python 2.6 and 2.7 using native
Windows and the Cygwin environment. It should run without issues on any POSIX
platform. As of 2012/8/5 The PIL installed with Cygwin's Python 2.6
misbehaves slightly by printing "Aborted" when the program ends.

For Windows users there is a binary installer available as well.

	
Running
-------
The simplest way to run the colorizer is to supply the input file name:

``> colorize_lecroy -i <input>``

This will produce a color output image named ``color_<input>.png`` using the default color style.
If you want to control the output file name and format, specify it with the ``-o <output>`` switch.

You can use alternate predefined color styles or supply your own color definitions in a settings file passed with the ``-s`` switch:

``> colorize_lecroy -i captured_image.bmp -o colorized_image.png -s my_colors.cfg``

The predefined color styles are:

93xx
  A reproduction of the monochrome yellow appearance of the 93xx CRTs
analog
  A teal scheme that mimics a monochromatic analog scope display
gray
  A grayscale image
gray_nomenu
  Grayscale with the menu blanked
light
  A light colored image suitable for color printed output
waverunner
  Purple themed style mimicing a Waverunner display


Trace Reconstruction
~~~~~~~~~~~~~~~~~~~~
The black and white images produced by a screen dump on the scope don't
distinguish the grid lines and traces. By default the colorizer attempts to
reconstruct the portions of the traces that cross the grid lines. These can be
colored independently using the "Trace-Reconstruction" color. The
reconstruction is achieved through Boolean operations on the original image. It
is mostly accurate but can produce small artifacts. The ``-r`` option is used to
disable the reconstruction and show the grids overlaid on top of the traces.


Capturing A Screen Image
------------------------
The 93xx series scopes provide a wide range of methods for saving data. The
only commonly available method on all scopes is to use the serial or GPIB
ports. With a suitable cable you can connect to the scope under Windows using
the `ScopeExplorer <http://www.lecroy.com/support/softwaredownload/scopeexplorer.aspx>`_
utility. On other platforms you will need to send the ``SCDP`` command and
process the data transmitted by by the scope.

If a floppy drive is installed and working it is another avenue for saving
images captured on the scope.

The front panel PCCard slot only handles SRAM cards which are not well
supported with modern operating systems. However, if you have the type-3 hard
drive option on the back, you can use a more modern CF card with an adapter to
capture data to flash memory.

To capture an image of the screen you need to select the desired output. Press
the "Utilities" button, then select "Hardcopy Setup". From there select an
output destination. If you are using GPIB or the serial port you will need to
configure parameters under "GPIB/RS232 Setup".

Once the output destination is set, you can capture an image by pressing the
"Screen Dump" button on the front panel.


Licensing
---------
This program is open sourced under the MIT license.
See LICENSING.txt for the full license.
