Introduction
=============

.. note::
    The product has been renamed from *VIRL* to *Cisco Modeling Labs* /
    CML 2. References to VIRL still exist in the product documentation and within
    code or examples.

    The name of the package itself has not been changed. Throughout the
    documentation it is referred to as "virl2_client", "Python Client Library"
    or "PCL".

This is the client library for the Cisco Modeling Labs Platform
(``virl2_client``). It provides a Python package to programmatically create,
edit, delete and control network simulations on a CML 2 controller.

It is a pure Python implementation that requires Python 3. We've written and
tested the package with Python 3.8.10.

The status of the package can be considered **stable**.  Issues with the software
should be raised via the `GitHub issue tracker <https://github.com/CiscoDevNet/virl2-client/issues>`_.

Use Case Description
*********************

The client library provides a convenient interface to control the lifecycle of a
network simulation. This can be used for automation scripts directly in Python
but also for third party integrations / plugins which need to integrate with a
simulated network. Examples already existing are an `Ansible plugin
<https://github.com/CiscoDevNet/ansible-virl/>`_.

Installation
*************

The package comes in form of a wheel that is downloadable from the CML 2
controller. The package can be installed either from PyPI using::

    pip3 install virl2_client

If you want to interact with devices via the client library, you need to
also install the pyATS library. This can be achieved in one go using::

    pip3 install "virl2_client[pyats]"

Note that this does *not* pull in the full pyATS package... See below how that is achieved.

Alternatively, the version that is bundled with the CML 2 controller can be
downloaded to the local filesystem and then directly installed via::

    pip3 install ./virl2_client-*.whl

The bundled version is available on the index site of the docs when
viewed directly on the CML 2 controller.

Ensure to replace use the correct file name, replacing the wildcard with the
proper version/build information. For example::

    pip3 install virl2_client-2.0.0b10-py3-none-any.whl

We recommend the use of a virtual environment for installation.

If you require the full version of the pyATS library including things like Genie
then you need to do this in a subsequent step like shown here::

    pip3 install "pyats[full]"

.. warning::
    The version of the Python client library must be compatible with the version
    of the controller.  If you are running an older controller version then it's
    likely that the latest client library version from PyPI can **not** be used.
    In this case, you need to either use the version available from the
    controller itself or by specifying a version constraint.

    Example: When on a controller version 2.2.x, then you'd need to install with
    ``pip3 install "virl2-client<2.3.0"``. This will ensure that the version
    installed is compatible with 2.2.x.

Usage
******

The package itself is fairly well documented using docstrings. In addition, the
documentation is available in HTML format on the controller itself, via the
"Tools -> Client Library" menu.

Get started with the ``ClientLibrary`` class
:class:`virl2_client.virl2_client.ClientLibrary`
and the ``Lab`` :class:`virl2_client.models.lab.Lab` class.

Compatibility
**************

This package and the used API is specific to CML 2. It is not backwards
compatible with VIRL 1.x and therefore can not be used with VIRL 1.x. If you are
looking for a convenient tool to interface with the VIRL 1 API then the `VIRL
Utils tool <https://github.com/CiscoDevNet/virlutils>`_ is recommended.

Known Issues
*************

There are no major known issues at this point. See the comment in the
*Introduction* section. Also, see the *Issues* section in GitHub to learn about
known issues or raise new ones, if needed.  Also see ``CHANGES.md``.

Getting Help
*************

If you have questions, concerns, bug reports, etc., please create an issue
against the `repository on GitHub <https://github.com/CiscoDevNet/virl2-client/>`_.

Getting Involved
*****************

We welcome contributions. Whether you fixed a bug, added a new feature or
corrected a typo, all contributions are welcome. General instructions on how to
contribute can be found in the ``CONTRIBUTING`` file.

Licensing Info
***************

This code is licensed under the Apache 2.0 License. See LICENSE for
details.

References
***********

This package is part of the CML 2 Network Simulation platform.
For details, go to `<https://developer.cisco.com/modeling-labs>`_.  Or to
`<https://developer.cisco.com/docs/virl2-client/>`_.
