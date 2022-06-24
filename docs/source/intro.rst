Introduction
=============

This is the client library for the Cisco VIRL :sup:`2` Network Simulation Platform
(``virl2_client``). It provides a Python package to programmatically create, edit,
delete and control network simulations on a VIRL :sup:`2` controller.

It is a pure Python implementation that requires Python3. We've written and tested
the package with Python 3.8.10.

The **status** of this package can be considered **Beta**. We're not aware of
any major issues at the time of release. However, since this is the first
release of the package, bugs might exist. Both in the package as well as in the
API implementation on the controller.

Use Case Description
*********************

The client library provides a convenient interface to control the lifecycle of a
network simulation running on VIRL2. This can be used for automation scripts
directly in Python but also for third party integrations / plugins which need to
integrate with a simulated network. Examples already existing are an `Ansible
plugin <https://github.com/CiscoDevNet/ansible-virl/>`_.

Installation
*************

The package comes in form of a wheel that is downloadable from the VIRL
controller. The package can be installed either from PyPi using::

    pip install virl2_client

or, alternatively, the version that is bundled with the VIRL :sup:`2` controller
can be downloaded to the local filesystem and then directly installed via::

    pip install ./virl2_client-*.whl

The bundled version is available on the index site of the docs when
viewed directly on the VIRL :sup:`2` controller.

We recommend the use of a virtual environment for installation.

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

This package and the used API is specific to VIRL :sup:`2`. It is not backwards
compatible with VIRL 1.x and therefore can not be used with VIRL 1.x. If you
are looking for a convenient tool to interface with the VIRL 1 API then the
`VIRL Utils tool <https://github.com/CiscoDevNet/virlutils>`_ is recommended.

Known Issues
*************

There are no known issues at this point. See the comment in the *Introduction*
section.

Getting Help
*************

If you have questions, concerns, bug reports, etc., please create an issue
against the `repository on GitHub <https://github.com/CiscoDevNet/virl2-client/>`_.

Getting Involved
*****************

We welcome contributions. Whether you fixed a bug, added a new feature or
corrected a typo, all contributions are welcome. General instructions on how to
contribute can be found in the CONTRIBUTING file.

Licensing Info
***************

This code is licensed under the Apache 2.0 License. See LICENSE for
details.

References
***********

This package is part of the VIRL :sup:`2` Network Simulation platform.
For details, go to `<https://developer.cisco.com/modeling-labs>`_.  Or to
`<https://developer.cisco.com/docs/virl2-client/>`_.
