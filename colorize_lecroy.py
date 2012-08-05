#!/usr/bin/python
# -*- coding: utf-8 -*-

# Lecroy 93xx colorizer
# Colorizes black and white screen captures from Lecroy 93xx series oscilloscopes

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

import sys
import os
import ast

from optparse import OptionParser
from ConfigParser import SafeConfigParser

import PIL
from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw

# Screen capture dimensions are 832x696
IMAGE_SIZE = (832,696)

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
            # read the image
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
            
            if match: # all pixel tests passed
                return key
        
        return 'Unknown'


    def colorize(self, in_file, no_reconstruct):
        '''colorize the input image'''
        im = Image.open(in_file).convert('RGB')
        mim = im.convert('1')
        cim = im.copy()

        mask_bg = Image.new('RGB',IMAGE_SIZE,(0,0,0))

        # colorize the regions around the perimeter
        m = mask_bg.copy()
        m_drawer = ImageDraw.Draw(m)
        for key, box in self.settings.regions.items():
            m_drawer.rectangle(box, fill=self.settings.colors[key])


        # identify the grid type
        grid_name = self.identify_grid(im)
        if grid_name == 'Unknown':
            raise ValueError, 'Cannot identify image grid'

        # colorize additional regions for special grids
        if grid_name == 'param':
            m_drawer.rectangle(self.settings.opt_regions['parameters'], fill=self.settings.colors['parameters'])
        elif grid_name[0:2] == 'xy':
            xy_curs_box = self.settings.opt_regions['xy-cursors']
            m_drawer.rectangle(self.settings.opt_regions['xy-cursors'], fill=self.settings.colors['xy-cursors'])

        # find the bottommost grid so we can colorize the strip where the trigger delay marker
        # appears.
        max_y = 0
        for box in self.settings.grid_boxes[grid_name]:
            if box[3] > max_y:
                max_y = box[3]

        delay_box = (self.settings.regions['left-marker'][0], max_y, self.settings.regions['right-marker'][2],max_y + 25)
        m_drawer.rectangle(delay_box, fill=self.settings.colors['left-marker'])


        # colorize the traces
        for box in self.settings.grid_boxes[grid_name]:
            m_drawer.rectangle(box, fill=self.settings.colors['trace'])

        del m_drawer

        # sreeen the colorized regions onto the image
        cim = ImageChops.screen(cim, m)


        # create the background image
        bg_im = Image.new('RGB', im.size, self.settings.colors['background'])
        bg_im_drawer = ImageDraw.Draw(bg_im)
        
        # add the grid backgrounds
        for box in self.settings.grid_boxes[grid_name]:
            bg_im_drawer.rectangle(box, fill=self.settings.colors['grid-background'])
            
        del bg_im_drawer


        # create the grid mask
        grid_image_file = os.path.join(self.settings.script_dir, 'data', self.settings.grids[grid_name][GRID_IMAGE])
        gr_im = Image.open(grid_image_file).convert('RGB')
        gr_mask = gr_im.convert('1')

        # add the colored grid lines to the background
        gline_im = Image.new('RGB', im.size, self.settings.colors['grid'])
        bg_im = Image.composite(bg_im, gline_im, gr_mask)


        # remove the grid from the original image mask
        ol_mask = ImageChops.subtract(ImageChops.invert(mim), ImageChops.invert(gr_mask))

        # overlay the colorized imagery over the background
        cim = Image.composite(cim, bg_im, ol_mask)


        if not no_reconstruct:
            # reconstruct the trace portions covered by the grid
            
            # isolate the horizontal lines in the grid
            # shift the grid mask left and right
            sl_grm = ImageChops.offset(gr_mask, -1,0)
            sr_grm = ImageChops.offset(gr_mask, 1,0)
            
            h_grm = ImageChops.logical_and(ImageChops.add(sr_grm, gr_mask), ImageChops.add(sl_grm, gr_mask))

            # isolate the vertical  lines in the grid
            # shift the grid mask up and down
            su_grm = ImageChops.offset(gr_mask, 0,-1)
            sd_grm = ImageChops.offset(gr_mask, 0,1)
            
            v_grm = ImageChops.logical_and(ImageChops.add(sd_grm, gr_mask), ImageChops.add(su_grm, gr_mask))

            # find where a horizontal grid line is bounded by trace pixels above and below
            su_mim = ImageChops.offset(mim, 0,-1)
            sd_mim = ImageChops.offset(mim, 0,1)
            h_mim = ImageChops.logical_or(su_mim, sd_mim)
            h_mim = ImageChops.logical_or(h_mim, ImageChops.logical_or(ImageChops.invert(v_grm),h_grm))

            # find where a vertical grid line is bounded by trace pixels left and right
            sl_mim = ImageChops.offset(mim, -1,0)
            sr_mim = ImageChops.offset(mim, 1,0)
            v_mim = ImageChops.logical_or(sl_mim, sr_mim)
            v_mim = ImageChops.logical_or(v_mim, ImageChops.logical_or(ImageChops.invert(h_grm),v_grm))

            # fill in cross points of horiz. and vert. lines if upper left and lower right corners have
            # pixels from a trace
            sul_mim = ImageChops.offset(mim, -1,-1)
            sdr_mim = ImageChops.offset(mim, 1,1)
            d_mim = ImageChops.logical_or(sul_mim, sdr_mim)
            d_mim = ImageChops.logical_or(d_mim, ImageChops.logical_or(h_grm, v_grm))
            
            recon = ImageChops.logical_and(h_mim, v_mim)
            recon = ImageChops.logical_and(recon, d_mim)

            # mask out the grid borders from the reconstruction
            m = Image.new('1', IMAGE_SIZE, 1)
            m_drawer = ImageDraw.Draw(m)
            for box in self.settings.grid_boxes[grid_name]:
                m_drawer.rectangle(box, 0)
            del m_drawer
            
            recon = ImageChops.logical_or(recon, m)
            
            # composite the reconstructed trac segments onto the colorized image
            ol_color = Image.new('RGB', IMAGE_SIZE, self.settings.colors['trace-reconstruction'])
            cim = ImageChops.composite(cim, ol_color, recon)

        return cim

    
class ColorizerSettings(object):
    '''process the option settings files'''
    def __init__(self, setting_file=None, defaults_file=None, script_dir=None):
        self.script_dir = script_dir
        
        self.colors = {}
        self.regions = {}
        self.opt_regions = {}
        self.grids = {}
        self.grid_boxes = {}
        self.grid_test_points = {}
        
        if not defaults_file is None:
            default_settings = self.get_settings(defaults_file)
            self.colors = default_settings['colors']
            self.regions = default_settings['regions']
            self.opt_regions = default_settings['optional regions']
            self.grids = default_settings['grids']
            self.grid_boxes = default_settings['grid boxes']
            self.grid_test_points = default_settings['grid test points']

        if not setting_file is None:
            settings = self.get_settings(setting_file)
            if 'colors' in settings: self.colors.update(settings['colors'])
            if 'regions' in settings: self.regions.update(settings['regions'])
            if 'optional regions' in settings: self.opt_regions.update(settings['optional regions'])
            if 'grids' in settings: self.grids.update(settings['grids'])
            if 'grid boxes' in settings: self.grids.update(settings['grid boxes'])
            if 'grid test points' in settings: self.grids.update(settings['grid test points'])

        
    def get_settings(self, setting_file):
        parser = SafeConfigParser()
        parser.read(setting_file)
        
        settings = {}
        settings['colors'] = {}
        if 'colors' in parser.sections():
            settings['colors'] = dict(parser.items('colors'))
            
            # validate the colors
            for k, v in settings['colors'].items():
                try:
                    rgb = PIL.ImageColor.getrgb(v)
                except ValueError:
                    print('error: Invalid color format {0} = {1} in file {2}'.format(k, v, setting_file))
                    sys.exit(-1)
                else:
                    settings['colors'][k] = rgb


        for section in ['regions', 'optional regions', 'grids', 'grid boxes', 'grid test points']:
            settings[section] = {}
            if section in parser.sections():
                settings[section] = dict([(k, ast.literal_eval(v)) for k, v in parser.items(section)])
        
        return settings
        
        
if __name__ == '__main__':
    print('Lecroy 93xx colorizer\n')

    # process arguments
    usage = '''%prog -i input -o output [-s settings] [-r]
  Any image format suported by the Python Imaging Library is supported
  for input and output.
  See http://www.pythonware.com/library/pil/handbook/index.htm#appendixes'''
    parser = OptionParser(usage=usage)
    parser.add_option('-i', dest='in_file', help='input image')
    parser.add_option('-o', dest='out_file', help='output image')
    parser.add_option('-s', '--settings', dest='setting_file', help='settings to control colors and configuration')
    parser.add_option('-r', '--no-reconstruction', action='store_true', default=False, dest='no_reconstruct', help='disable trace reconstruction over grid')

    options, args = parser.parse_args()

    # validate options
    if options.in_file is None:
        print('error: Missing input file\n')
        parser.print_help()
        sys.exit(-1)

    if not os.path.exists(options.in_file):
        print('error: Input file ({0}) does not exist.\n'.format(options.in_file))
        parser.print_help()
        sys.exit(-1)

    if options.out_file is None:
        print('error: Missing output file\n')
        parser.print_help()
        sys.exit(-1)

    if not options.setting_file is None and not os.path.exists(options.setting_file):
        print('error: Settings file ({0}) does not exist.\n'.format(options.setting_file))
        parser.print_help()
        sys.exit(-1)
        
    # find the default settings
    script_dir = os.path.dirname(os.path.realpath(__file__))
    defaults_file = os.path.join(script_dir, 'data', 'default_settings.cfg')
    if not os.path.exists(defaults_file):
        print('error: Unable to find default settings file ({0}).'.format(defaults_file))
        sys.exit(-1)
    
    # get the settings
    settings = ColorizerSettings(setting_file=options.setting_file, defaults_file=defaults_file, script_dir=script_dir)

    
    # colorize the image
    colorizer = LecroyColorizer(settings)

    print('  Reading image:', options.in_file)
    try:
        color_im = colorizer.colorize(options.in_file, options.no_reconstruct)
    except ValueError as e:
        print('error: {0}'.format(e.message))
        sys.exit(-1)

    grid_name = colorizer.identify_grid(options.in_file)
    print('  Grid type:', settings.grids[grid_name][GRID_DESCR])

    print('  Saving colorized image:', options.out_file)
    color_im.save(options.out_file)
    sys.exit(0)
