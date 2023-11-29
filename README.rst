Introduction
============


.. image:: https://readthedocs.org/projects/adafruit-circuitpython-pycamera/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/pycamera/en/latest/
    :alt: Documentation Status


.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord


.. image:: https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/actions
    :alt: Build Status


.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code Style: Black

Library for the Adafruit PyCamera


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_
* `Bus Device <https://github.com/adafruit/Adafruit_CircuitPython_BusDevice>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.



.. ::
    `Purchase one from the Adafruit shop <http://www.adafruit.com/products/9999>`_

Installing from PyPI
=====================

This package is available on PyPI so that it can be installed by Thonny. It is
not useful to install this package from PyPI on a Windows, Mac, or Linux
computer.

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_pycamera

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Usage Example
=============

.. code-block: python

    from adafruit_pycamera import PyCamera

    pycam = PyCamera()

    while True:
        new_frame = pycam.continuous_capture()
        # .. do something with new_frame

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/pycamera/en/latest/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
