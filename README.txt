LeCroy 93xx colorizer
Version: 1.0

Colorize black and white screen captures from Lecroy 93xx series oscilloscopes.

Dependencies
------------
	* Python 2.6 or newer. Not tested under Python 3
	* Python Imaging Library (PIL)

Installation
------------

	
The LeCroy colorizer has been tested on Python 2.6 and 2.7 using native
Windows and the Cygwin environment. It should run without issues on any POSIX
platform. As of 2012/8/5 The PIL installed with Cygwin's Python 2.6
misbehaves slightly by printing "Aborted" when the program ends.
	
Running
-------
The simplest way to run the colorizer is to supply the input and output file
names:

> colorize_lecroy -i <input> -o <output>

This will produce a color output image in the format determined by the file
extension using the default color style.

You can use alternate predefined color styles or supply your own color
definitions in a settings file passed with the `-s` switch:

> colorize_lecroy -i captured_image.bmp -o colorized_image.png -s my_colors.cfg


The predefined color styles are:
  * 93xx - A reproduction of the monochrome yellow appearance of the 93xx CRTs
  * analog - A teal scheme that mimics a monochromatic analog scope display
  * gray - A grayscale image
  * gray_nomenu - Grayscale with the menu blanked
  * light - A light colored image suitable for color printed output
  * waverunner - Purple themed style mimicing a Waverunner display

The monochromatic images produced by a screen dump on the scope don't
distinguish the grid lines and traces. By default the colorizer attempts to
reconstruct the portions of the traces that cross the grid lines. These can be
colored independently using the "Trace-Reconstruction" color. The
reconstruction is achieved through Boolean operations on the original image.
It is mostly accurate but can produce small artifacts. The `-r` option is used
to disable the reconstruction and show the grids overlaid on top of the traces.

Licensing
---------
This program is open sourced under the MIT license.
See LICENSING.txt for the full license.

Documentation
-------------


	