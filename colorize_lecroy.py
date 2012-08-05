#!/usr/bin/python

from __future__ import print_function

import sys
import os
import ast

from optparse import OptionParser
from ConfigParser import SafeConfigParser

import PIL
from PIL import Image
from PIL import ImageChops

# Screen capture dimensions are 832x696

GRID_ID = 0
GRID_IMAGE = 1
GRID_DESCR = 2

class Colorizer(object):
    ''' Colorizes screen captures from Lecroy 93xx series oscilloscopes '''

    def __init__(self, settings):
        self.settings = settings

    def identify_grid(self, im):
        bw_im = im.convert('1')

        for key in self.settings.grid_test_points.keys():
            points = self.settings.grid_test_points[key]
            wp = points[0]
            bp = points[1]
            
            match = True
            if wp != None:
                for tp in wp:
                    if bw_im.getpixel(tp) != 255:
                        match = False
                        break
            
            if bp != None:
                for tp in bp:
                    if bw_im.getpixel(tp) != 0:
                        match = False
                        break
            
            if match: # all pixel tests passed
                return key
        
        return 'Unknown'


    def colorize(self, in_file, no_reconstruct):
        im = Image.open(in_file).convert('RGB')
        mim = im.convert('1')
        cim = im.copy()

        mask_bg = Image.new('RGB',(832,696),(0,0,0))

        # colorize the regions around the perimeter
        m = mask_bg.copy()
        for key, box in self.settings.regions.items():
            bi = Image.new('RGB', (box[2]-box[0], box[3]-box[1]), self.settings.colors[key])
            m.paste(bi,box)

        # identify the grid type
        grid_name = self.identify_grid(im)
        print('  Grid type:', self.settings.grids[grid_name][GRID_DESCR])


        # colorize additional regions for special grids
        if grid_name == 'param':
            param_box = self.settings.opt_regions['parameters']
            bi = Image.new('RGB', (param_box[2]-param_box[0], param_box[3]-param_box[1]), self.settings.colors['parameters'])
            m.paste(bi,param_box)
        elif grid_name[0:2] == 'xy':
            xy_curs_box = self.settings.opt_regions['xy-cursors']
            bi = Image.new('RGB', (xy_curs_box[2]-xy_curs_box[0], xy_curs_box[3]-xy_curs_box[1]), self.settings.colors['xy-cursors'])
            m.paste(bi,xy_curs_box)

        # find the bottom most grid so we can colorize the strip where the trigger delay marker
        # appears.
        max_y = 0
        for box in self.settings.grid_boxes[grid_name]:
            if box[3] > max_y:
                max_y = box[3]

        delay_box = (self.settings.regions['left-marker'][0], max_y, self.settings.regions['right-marker'][2],max_y + 25)
        bi = Image.new('RGB', (delay_box[2]-delay_box[0], delay_box[3]-delay_box[1]), self.settings.colors['left-marker'])
        m.paste(bi,delay_box)


        # colorize the traces
        for box in self.settings.grid_boxes[grid_name]:
            bi = Image.new('RGB', (box[2]-box[0], box[3]-box[1]), self.settings.colors['trace'])
            m.paste(bi, box)


        # sreeen the colorized regions onto the image
        cim = ImageChops.screen(cim, m)



        #gr_im = ImageChops.invert(gr_im)
        #cim = ImageChops.add(cim, gr_im)


        # create the background image
        bg_im = Image.new('RGB', im.size, self.settings.colors['background'])
        
        # add the grid backgrounds
        for box in self.settings.grid_boxes[grid_name]:
            bi = Image.new('RGB', (box[2]-box[0], box[3]-box[1]), self.settings.colors['grid-background'])
            bg_im.paste(bi, box)


        # create the grid mask
        gr_im = Image.open(os.path.join('data',self.settings.grids[grid_name][GRID_IMAGE])).convert('RGB')
        gr_mask = gr_im.convert('1')

        # add the colored grid lines to the background
        gline_im = Image.new('RGB', (832,696), self.settings.colors['grid'])
        bg_im = Image.composite(bg_im, gline_im, gr_mask)


        # remove the grid from the original image mask
        ol_mask = ImageChops.subtract(ImageChops.invert(mim), ImageChops.invert(gr_mask))

        # overlay the colorized imagery over the background
        cim = Image.composite(cim, bg_im, ol_mask)


        if not no_reconstruct:
            # reconstruct the portions covered by the grid
            
            # isolate the horizontal lines in the grid
            # shift the grid mask left and right
            sl_grm = ImageChops.offset(gr_mask, -1,0)
            sr_grm = ImageChops.offset(gr_mask, 1,0)
            
            h_grm = ImageChops.add(sl_grm, gr_mask)
            h_grm = ImageChops.logical_and(ImageChops.add(sr_grm, gr_mask), h_grm)

            # isolate the vertical  lines in the grid
            # shift the grid mask up and down
            su_grm = ImageChops.offset(gr_mask, 0,-1)
            sd_grm = ImageChops.offset(gr_mask, 0,1)
            
            v_grm = ImageChops.add(su_grm, gr_mask)
            v_grm = ImageChops.logical_and(ImageChops.add(sd_grm, gr_mask), v_grm)

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
            m = Image.new('1', (832,696), 1)
            for box in self.settings.grid_boxes[grid_name]:
                bi = Image.new('1', (box[2]-box[0]-1, box[3]-box[1]-1), 0)
                m.paste(bi, (box[0]+1, box[1]+1, box[2], box[3]))
            
            recon = ImageChops.logical_or(recon, m)
            
            ol_color = Image.new('RGB', (832,696), self.settings.colors['trace-reconstruction'])
            cim = ImageChops.composite(cim, ol_color, recon)

        return cim

    
class ColorizerSettings(object):
    def __init__(self, setting_file=None, defaults_file=None):
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
                    sys.exit(-1)
                else:
                    settings['colors'][k] = rgb


        for section in ['regions', 'optional regions', 'grids', 'grid boxes', 'grid test points']:
            settings[section] = {}
            if section in parser.sections():
                settings[section] = dict([(k, ast.literal_eval(v)) for k, v in parser.items(section)])
        
        return settings
        
        
if __name__ == '__main__':
	#cf = colorize(sys.argv[1])
	#cf.save('test.png')
    
    # process arguments
    parser = OptionParser()
    parser.add_option('-i', dest='in_file', help='Input file')
    parser.add_option('-o', dest='out_file', help='Input file')
    parser.add_option('-s', '--settings', dest='setting_file', help='Use settings to control colors')
    parser.add_option('-r', '--no-reconstruction', action='store_true', default=False, dest='no_reconstruct', help='Disable trace reconstruction over grid')

    options, args = parser.parse_args()

    # validate options
    if options.in_file is None:
        print('error: Missing input file')
        parser.print_help()
        sys.exit(-1)

    if not os.path.exists(options.in_file):
        print('error: Input file ({0}) does not exist.'.format(options.in_file))
        parser.print_help()
        sys.exit(-1)

    if options.out_file is None:
        print('error: Missing output file')
        parser.print_help()
        sys.exit(-1)

    if not options.setting_file is None and not os.path.exists(options.setting_file):
        print('error: Settings file ({0}) does not exist.'.format(options.setting_file))
        parser.print_help()
        sys.exit(-1)
        
    # find the default settings
    script_dir = os.path.dirname(os.path.realpath(__file__))
    defaults_file = os.path.join(script_dir, 'data', 'default_settings.cfg')
    if not os.path.exists(defaults_file):
        print('error: Unable to find default settings file ({0}).'.format(defaults_file))
        sys.exit(-1)
    
    # get the settings
    if not options.setting_file is None and os.path.exists(options.setting_file):
        settings = ColorizerSettings(options.setting_file, defaults_file)
    else:
        # just use defaults
        settings = ColorizerSettings(defaults_file=defaults_file)

        
    # colorize image
    print('Lecroy 93xx colorizer')
    
    colorizer = Colorizer(settings)

    print('  Reading image:', options.in_file)
    color_im = colorizer.colorize(options.in_file, options.no_reconstruct)

    print('  Saving colorized image:', options.out_file)
    color_im.save(options.out_file)
