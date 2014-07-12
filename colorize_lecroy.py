#!/usr/bin/python
# -*- coding: utf-8 -*-

'''LeCroy 93xx colorizer
Colorize black and white screen captures from Lecroy 93xx series
oscilloscopes'''

# Copyright © 2012 Kevin Thibedeau

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import print_function

__version__ = '1.2'

import sys
import os
import ast
import re

from optparse import OptionParser

import ConfigParser
from ConfigParser import SafeConfigParser

import PIL
from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw

# Screen capture dimensions are 832x696
IMAGE_SIZE = (832, 696)

GRID_ID = 0
GRID_IMAGE = 1
GRID_DESCR = 2

class LecroyColorizer(object):
    '''Colorize screen captures from Lecroy 93xx series oscilloscopes'''

    def __init__(self, settings):
        self.settings = settings

    def identify_grid(self, im):
        '''Identify which grid is used in the image'''
        
        if not isinstance(im, Image.Image):
            # Read the image
            im = Image.open(im)

        bw_im = im.convert('1')

        for key in self.settings.grid_test_points.keys():
            points = self.settings.grid_test_points[key]
            white_pixels = points[0]
            black_pixels = points[1]
            
            match = True
            if white_pixels != None:
                for tp in white_pixels:
                    if bw_im.getpixel(tp) != 255:
                        match = False
                        break
            
            if black_pixels != None:
                for tp in black_pixels:
                    if bw_im.getpixel(tp) != 0:
                        match = False
                        break
            
            if match: # All pixel tests passed
                return key
        
        return 'Unknown'


    def colorize(self, in_file, no_reconstruct):
        '''colorize the input image'''
        im = Image.open(in_file).convert('RGB')


        # Validate the image to ensure it is from a 93xx scope
        valid = True
        if im.size != IMAGE_SIZE: valid = False
        
        # The histogram should have all values at 0 and 255 with nothing but 0's in between
        red_hist = im.histogram()[:256]
        for color in red_hist[1:255]:
            if color != 0: valid = False
            
        if not valid:
            raise ValueError, 'Not a proper {0[0]}x{0[1]} black and white image'.format(IMAGE_SIZE)

        # The image is valid... proceed
        mim = im.convert('1')
        cim = im.copy()


        mask_bg = Image.new('RGB', IMAGE_SIZE, (0, 0, 0))

        # Colorize the regions around the perimeter
        m = mask_bg.copy()
        m_drawer = ImageDraw.Draw(m)
        for key, box in self.settings.regions.items():
            m_drawer.rectangle(box, fill=self.settings.colors[key])

        # Identify the grid type
        grid_name = self.identify_grid(im)
        if grid_name == 'Unknown':
            raise ValueError, 'Cannot identify image grid'

        # Colorize additional regions for special grids
        if grid_name == 'param':
            m_drawer.rectangle(self.settings.opt_regions['parameters'], fill=self.settings.colors['parameters'])
            m_drawer.rectangle(self.settings.opt_regions['parameters-span'], fill=self.settings.colors['parameters-span'])
        elif grid_name[0:2] == 'xy':
            m_drawer.rectangle(self.settings.opt_regions['xy-cursors'], fill=self.settings.colors['xy-cursors'])
            
        # Find the bottommost grid so we can colorize the strip where the trigger delay marker
        # appears.
        max_y = 0
        for box in self.settings.grid_boxes[grid_name]:
            if box[3] > max_y:
                max_y = box[3]

        if grid_name == 'xy':
            delay_box_height = 35
        else:
            delay_box_height = 25
        delay_box = (self.settings.regions['left-marker'][0], max_y, self.settings.regions['right-marker'][2], max_y + delay_box_height)
        m_drawer.rectangle(delay_box, fill=self.settings.colors['left-marker'])

        # Colorize the traces
        for box in self.settings.grid_boxes[grid_name]:
            m_drawer.rectangle(box, fill=self.settings.colors['trace'])

        # Find the boxes for the channel labels and the menu buttons
        channel_boxes, menu_boxes = self._find_boxes(mim)
            
        # Paint the text for the channel and menu boxes
        for box in channel_boxes:
            adj_box = (box[0] + 1, box[1] + 12, box[2] - 1, box[3] - 1)
            m_drawer.rectangle(adj_box, fill=self.settings.colors['channels-text'])

        for box in menu_boxes:
            adj_box = (box[0] + 1, box[1] + 12, box[2] - 1, box[3] - 1)
            m_drawer.rectangle(adj_box, fill=self.settings.colors['menu-text'])
            
        del m_drawer
        
        #m.save('regions.png')

        # Sreeen the colorized regions onto the image
        cim = ImageChops.screen(cim, m)


        # Create the background image
        bg_im = Image.new('RGB', im.size, self.settings.colors['background'])
        bg_im_drawer = ImageDraw.Draw(bg_im)
        
        # Add the grid backgrounds
        for box in self.settings.grid_boxes[grid_name]:
            bg_im_drawer.rectangle(box, fill=self.settings.colors['grid-background'])

        # Fill the channel and menu box backgrounds
        for box in channel_boxes:
            bg_im_drawer.rectangle(box, fill=self.settings.colors['channels-background'])
        for box in menu_boxes:
            bg_im_drawer.rectangle(box, fill=self.settings.colors['menu-background']) 
            
        del bg_im_drawer
        

        # Create the grid mask
        grid_image_file = os.path.join(self.settings.script_dir, 'data', self.settings.grids[grid_name][GRID_IMAGE])
        gr_im = Image.open(grid_image_file).convert('RGB')
        gr_mask = gr_im.convert('1')

        # Add the colored grid lines to the background
        gline_im = Image.new('RGB', im.size, self.settings.colors['grid'])
        bg_im = Image.composite(bg_im, gline_im, gr_mask)


        # Remove the grid from the original image mask
        ol_mask = ImageChops.subtract(ImageChops.invert(mim), ImageChops.invert(gr_mask))

        # Overlay the colorized imagery over the background
        cim = Image.composite(cim, bg_im, ol_mask)


        if not no_reconstruct:
            cim = self._reconstruct_trace(cim, gr_mask, mim, grid_name)

        return cim
        
    def _find_boxes(self, mim):
        '''Scan down a 1-pixel wide column to find the channel and menu box regions'''
        channel_box_column = self.settings.box_detection['channel-box-column']
        menu_box_column = self.settings.box_detection['menu-box-column']
        
        # Extract 1-pixel wide column from mask image
        channel_box_data = list(mim.crop(channel_box_column).getdata())
        channel_box_edges = self._find_box_edges(channel_box_data, channel_box_column[1])
        channel_boxes = []
        for edge in channel_box_edges:
            box = (channel_box_column[0] + 1, edge[0], channel_box_column[0] + 126, edge[1])
            channel_boxes.append(box)

        menu_box_data = list(mim.crop(menu_box_column).getdata())
        menu_box_edges = self._find_box_edges(menu_box_data, menu_box_column[1])
        menu_boxes = []
        for edge in menu_box_edges:
            box = (menu_box_column[0] + 1, edge[0], menu_box_column[0] + 136, edge[1])
            menu_boxes.append(box)
        
        return (channel_boxes, menu_boxes)

            
    def _find_box_edges(self, column_data, y_offset):
        '''Search a column for continuous spans of dark pixels signifying the edge of a box'''
        box_edges = []
        in_box = False
        box_start = 0
        for i in range(len(column_data)):
            if column_data[i] == 0 and not in_box:
                box_start = i
                in_box = True
            elif column_data[i] > 0 and in_box:
                # The XY grid cursors have pixels in the same column we're testing for channel box edges
                # Remove any edge that is too short to be a real box
                if i - box_start > 20: # Must be more than 20-pixels tall
                    box_edges.append((box_start + y_offset - 1, i + y_offset))
                in_box = False
        return box_edges
        
    def _reconstruct_trace(self, cim, gr_mask, mim, grid_name):
        '''Reconstruct the trace portions covered by the grid'''
        
        # Isolate the horizontal lines in the grid
        # Shift the grid mask left and right
        sl_grm = ImageChops.offset(gr_mask, -1, 0)
        sr_grm = ImageChops.offset(gr_mask, 1, 0)
        
        h_grm = ImageChops.logical_and(ImageChops.add(sr_grm, gr_mask), ImageChops.add(sl_grm, gr_mask))

        # Isolate the vertical  lines in the grid
        # Shift the grid mask up and down
        su_grm = ImageChops.offset(gr_mask, 0, -1)
        sd_grm = ImageChops.offset(gr_mask, 0, 1)
        
        v_grm = ImageChops.logical_and(ImageChops.add(sd_grm, gr_mask), ImageChops.add(su_grm, gr_mask))

        # Find where a horizontal grid line is bounded by trace pixels above and below
        su_mim = ImageChops.offset(mim, 0, -1)
        sd_mim = ImageChops.offset(mim, 0, 1)
        h_mim = ImageChops.logical_or(su_mim, sd_mim)
        h_mim = ImageChops.logical_or(h_mim, ImageChops.logical_or(ImageChops.invert(v_grm), h_grm))

        # Find where a vertical grid line is bounded by trace pixels left and right
        sl_mim = ImageChops.offset(mim, -1, 0)
        sr_mim = ImageChops.offset(mim, 1, 0)
        v_mim = ImageChops.logical_or(sl_mim, sr_mim)
        v_mim = ImageChops.logical_or(v_mim, ImageChops.logical_or(ImageChops.invert(h_grm), v_grm))

        # Fill in cross points of horiz. and vert. lines if upper left and lower right corners have
        # pixels from a trace
        sul_mim = ImageChops.offset(mim, -1, -1)
        sdr_mim = ImageChops.offset(mim, 1, 1)
        d_mim = ImageChops.logical_or(sul_mim, sdr_mim)
        d_mim = ImageChops.logical_or(d_mim, ImageChops.logical_or(h_grm, v_grm))
        
        recon = ImageChops.logical_and(h_mim, v_mim)
        recon = ImageChops.logical_and(recon, d_mim)

        # Mask out the grid borders from the reconstruction
        m = Image.new('1', IMAGE_SIZE, 1)
        m_drawer = ImageDraw.Draw(m)
        for box in self.settings.grid_boxes[grid_name]:
            m_drawer.rectangle(box, 0)
        del m_drawer
        
        recon = ImageChops.logical_or(recon, m)
        
        # Composite the reconstructed trac segments onto the colorized image
        ol_color = Image.new('RGB', IMAGE_SIZE, self.settings.colors['trace-reconstruction'])
        new_cim = ImageChops.composite(cim, ol_color, recon)
        
        return new_cim
    
class ColorizerSettings(object):
    '''process the option settings files'''
    def __init__(self, setting_file=None, defaults_file=None, script_dir=None):
        self.script_dir = script_dir
        
        self.colors = {}
        self.regions = {}
        self.opt_regions = {}
        self.box_detection = {}
        self.grids = {}
        self.grid_boxes = {}
        self.grid_test_points = {}
        
        if defaults_file is not None:
            default_settings = self.get_settings(defaults_file)
            self.colors = default_settings['colors']
            self.regions = default_settings['regions']
            self.opt_regions = default_settings['optional regions']
            self.box_detection = default_settings['box detection']
            self.grids = default_settings['grids']
            self.grid_boxes = default_settings['grid boxes']
            self.grid_test_points = default_settings['grid test points']

        if setting_file is not None:
            settings = self.get_settings(setting_file)
            if 'colors' in settings: self.colors.update(settings['colors'])
            if 'regions' in settings: self.regions.update(settings['regions'])
            if 'optional regions' in settings: self.opt_regions.update(settings['optional regions'])
            if 'box detection' in settings: self.box_detection.update(settings['box detection'])
            if 'grids' in settings: self.grids.update(settings['grids'])
            if 'grid boxes' in settings: self.grids.update(settings['grid boxes'])
            if 'grid test points' in settings: self.grids.update(settings['grid test points'])

        
    def get_settings(self, setting_file):
        '''Read the settings from a file into a plain dict'''
        parser = SafeConfigParser()
        
        try:
            parser.read(setting_file)
        
            settings = {}
            settings['colors'] = {}
            if 'colors' in parser.sections():
                settings['colors'] = dict(parser.items('colors'))
                
                # Validate the colors
                for k, v in settings['colors'].iteritems():
                    try:
                        rgb = PIL.ImageColor.getrgb(v)
                    except ValueError:
                        print('error: Invalid color format {0} = {1} in file {2}'.format(k, v, setting_file))
                        sys.exit(1)
                    else:
                        settings['colors'][k] = v #rgb


            for section in ['regions', 'optional regions', 'box detection', 'grids', 'grid boxes', 'grid test points']:
                settings[section] = {}
                if section in parser.sections():
                    try:
                        settings[section] = dict([(k, ast.literal_eval(v)) for k, v in parser.items(section)])
                    except ValueError:
                        raise ValueError, 'Unable to parse setting value in [{0}] section'.format(section)


        except ConfigParser.InterpolationMissingOptionError as e:
            e.file_name = setting_file
            raise e
        except ConfigParser.ParsingError as e:
            e.file_name = setting_file
            raise e
        except SyntaxError as e:
            e.file_name = setting_file
            raise e

                
        return settings


def adjust_colors(options, colors):
  '''Set regions identified as hidden to the background color and overridden colors'''
  for r, c in options.override_colors.iteritems():
    if r in colors:
      colors[r] = c


  for r in options.hide_regions:
    if r in colors:
      colors[r] = colors['background']

  if 'menu' in options.hide_regions:
    colors['menu-background']  = colors['background']
    colors['menu-text'] = colors['background']

  if 'channels' in options.hide_regions:
    colors['channels-background']  = colors['background']
    colors['channels-text'] = colors['background']




def apply_colors(override_colors, colors):
  '''Set colors specified on the command line'''

  for r, c in override_colors.iteritems():
    if r in colors:
      colors[r] = c

import shutil

def new_style_template(fname, script_dir):
  # Find the style template
  template_file = os.path.join(script_dir, 'data', 'style_template.cfg')
  if not os.path.exists(template_file):
    print('error: Unable to find default style template file ({0}).'.format(template_file))
    sys.exit(1)

  print('Copying style template to:', fname)
  shutil.copyfile(template_file, fname)


def main():
    '''Entry point for colorizer script'''
    print('LeCroy 93xx colorizer {0}\n'.format(__version__))
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Look up color styles
    color_styles = {}
    style_dir = os.path.join(script_dir, 'styles')
    if os.path.exists(style_dir):
        color_styles = dict([(os.path.splitext(v)[0], v) for v in os.listdir(style_dir)])
    
    # Process arguments
    usage = '''%prog [-i] input [-o output] [-s settings] [-r] [--hide=HIDE_REGIONS]
                          [--color=<name>:<color>[,...]]

       %prog --new-style=<file name>

  Any image format suported by the Python Imaging Library is supported
  for input and output.
  See http://www.pythonware.com/library/pil/handbook/index.htm#appendixes
  
  The settings can be a text file in ini format or one of the following
  style names:
    {0}'''.format(', '.join(sorted(color_styles.keys())))

    parser = OptionParser(usage=usage)
    parser.add_option('-i', dest='in_file', help='input image')
    parser.add_option('-o', dest='out_file', help='output image')
    parser.add_option('-s', '--settings', dest='setting_file', help='settings to control colors and configuration')
    parser.add_option('-r', '--no-reconstruction', action='store_true', default=False, dest='no_reconstruct', \
        help='disable trace reconstruction over grid')
    parser.add_option('--hide', dest='hide_regions', help='comma separated list of regions to hide')
    parser.add_option('--color', dest='override_colors', help='comma separated list of <name>:<color> pairs')
    parser.add_option('--new-style', dest='new_style', help='create a new style file from the default template')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
      help='verbose output')

    options, args = parser.parse_args()


    
    # Validate options

    if options.new_style is not None:
      new_style_template(options.new_style, script_dir)
      sys.exit(0)

    if not options.in_file:
      if len(args) > 0:
        options.in_file = args[0]

    if options.in_file is None:
        print('error: Missing input file\n')
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(options.in_file):
        print('error: Input file ({0}) does not exist.\n'.format(options.in_file))
        parser.print_help()
        sys.exit(1)

    if options.out_file is None:
        # Make the output file from the input name
        path, in_file = os.path.split(options.in_file)
        # We will prefer png output to minimize file size since PIL doesn't support RLE
        # for bitmaps.
        out_file = os.path.splitext('color_' + in_file)[0] + '.png'
        options.out_file = os.path.join(path, out_file)


    if options.setting_file is not None:
        print('  Style: {0}'.format(options.setting_file))
        # Check if the argument is a named style
        if options.setting_file in color_styles:
            options.setting_file = os.path.join(style_dir, color_styles[options.setting_file])

        if not os.path.exists(options.setting_file):
            print('error: Settings file ({0}) does not exist.\n'.format(options.setting_file))
            parser.print_help()
            sys.exit(1)


    try:
      if options.hide_regions is not None:
        options.hide_regions = set(r.strip().lower() for r in options.hide_regions.split(','))
        print('  Hide regions:', ', '.join(list(options.hide_regions)))
      else:
        options.hide_regions = set()
    except:
      parser.error('Invalid argument to --hide: {0}'.format(options.hide_regions))
      sys.exit(1)

    try:
      if options.override_colors is not None:
        # Preserve commas within rgb() and hsl() colors
        oc = re.sub(r'(,)(?=(?:[^()]|\([^)]*\))*$)', ';', options.override_colors)

        pairs = [c.split(':') for c in oc.split(';')]
        options.override_colors = dict((p[0].strip().lower(), p[1].strip()) for p in pairs)
        print('  Overriding colors:', ', '.join(['{0}:{1}'.format(k, v)
          for k, v in options.override_colors.iteritems()]))
      else:
        options.override_colors = {}
    except:
      parser.error('Invalid argument to --color: {0}'.format(options.override_colors))
      sys.exit(1)


    # Find the default settings
    defaults_file = os.path.join(script_dir, 'data', 'default_settings.cfg')
    if not os.path.exists(defaults_file):
        print('error: Unable to find default settings file ({0}).'.format(defaults_file))
        sys.exit(1)
    
    # Get the settings
    try:
        settings = ColorizerSettings(setting_file=options.setting_file, defaults_file=defaults_file, \
            script_dir=script_dir)
    except ConfigParser.InterpolationMissingOptionError as e:
        print('error: Unable to parse settings file {0}\n'.format(e.file_name) + e.message)
        sys.exit(1)
    except ConfigParser.ParsingError as e:
        print('error: Unable to parse settings file {0}\n'.format(e.file_name) + e.message)
        sys.exit(1)
    except ValueError as e:
        print('error: ' + e.message)
        sys.exit(1)
    except SyntaxError as e:
        print('error: ' + e.msg + ' in file ' + e.file_name)
        print('    ' + e.text)
        print('    ' + ' ' * (e.offset-1) + '^')
        sys.exit(1)


    # Apply hidden regions and override colors from the command line
    adjust_colors(options, settings.colors)

    if options.verbose:
      print('  Colors:')
      for c in sorted(settings.colors.keys()):
        if len(settings.colors[c]) == 3 and not isinstance(settings.colors[c], basestring):
          cval = 'rgb({0},{1},{2})'.format(*settings.colors[c])
        else:
          cval = settings.colors[c]
        print('    {0}: {1}'.format(c, cval))

    # Colorize the image
    colorizer = LecroyColorizer(settings)

    print('  Reading image:', options.in_file)
    try:
        color_im = colorizer.colorize(options.in_file, options.no_reconstruct)
    except ValueError as e:
        print('error: {0}'.format(e.message))
        sys.exit(1)

    grid_name = colorizer.identify_grid(options.in_file)
    print('  Grid type:', settings.grids[grid_name][GRID_DESCR])

    print('  Saving colorized image:', options.out_file)
    
    try:
        color_im.save(options.out_file)
    except IOError:
        print('error: Unable to write to file {0}'.format(options.out_file))
        sys.exit(1)
        
    sys.exit(0)

if __name__ == '__main__':
    main()

