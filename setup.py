from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup

# use README.rst for the long description
with open('README.rst') as fh:
    long_description = fh.read()
    
# scan the script for the version string
version_file = 'colorize_lecroy.py'
version = None
with open(version_file) as fh:
    try:
        version = [line.split('=')[1].strip().strip("'") for line in fh if line.startswith('__version__')][0]
    except IndexError:
        pass

if version is None:
    raise RuntimeError('Unable to find version string in file: {0}'.format(version_file))

setup(name='lecroy-colorizer',
    version=version,
    author='Kevin Thibedeau',
    author_email='kevin.thibedeau@gmail.com',
    url='http://code.google.com/p/lecroy-colorizer/',
    download_url='http://code.google.com/p/lecroy-colorizer/downloads/list',
    description='A utility to colorize black and white screen captures from LeCroy 93xx series oscilloscopes',
    long_description=long_description,
    install_requires = ['pillow >= 2.8.0'],
    packages = ['data', 'styles'],
    py_modules = ['colorize_lecroy'],
    entry_points = {
        'console_scripts': ['colorize_lecroy = colorize_lecroy:main']
    },
    include_package_data = True,
    
    use_2to3 = True,
    
    keywords='LeCroy oscilloscope',
    license='MIT',
    classifiers=['Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Topic :: Scientific/Engineering :: Visualization',
        'Topic :: Utilities'
        ]
    )
