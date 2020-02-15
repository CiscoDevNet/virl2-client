# VIRL 2 Client Library

## Introduction

This is the client library for the Cisco VIRL 2 Network Simulation Platform
(`virl2_client`). It provides a Python package to programmatically create, edit,
delete and control network simulations on a VIRL 2 controller.

It is a pure Python implementation that requires Python3. We've tested and
written the package with Python 3.6.8.

The **status** of this package can be considered **Beta**. We're not aware of
any major issues at the time of release. However, since this is the first
release of the package, bugs might exist. Both in the package as well as in the
API implementation on the controller itself.

## Use Case Description

The client library provides a convenient interface to control the lifecycle of a
network simulation. This can be used for automation scripts directly in Python
but also for third party integrations / plugins which need to integrate with a
simulated network. Examples already existing are an [Ansible
plugin](https://github.com/CiscoDevNet/ansible-virl).

## Installation

The package comes in form of a wheel that is downloadable from the VIRL
controller itself. It should also be available on PyPi after the release of
VIRL 2 itself. When available on PyPi, the package can be installed via

    pip3 install virl2_client

Otherwise, the wheel can be installed via

    pip3 install ./virl2_client-*.whl

Ensure to replace use the correct file name, replacing the wildcard with the
proper version/build information. For example

    pip3 install virl2_client-2.0.0b10-py3-none-any.whl

We recommend the use of a virtual environment for installation.

## Usage

The package itself is fairly well documented using docstrings. In addition, the
documentation is available in HTML format on the controller itself, via the
"Tools -> Client Library" menu.

## Known Issues

There are no known issues at this point. See the comment in the *Introduction*
section.

## Getting Help

If you have questions, concerns, bug reports, etc., please create an issue
against this repository.

## Getting Involved

We welcome contributions. Whether you fixed a bug, added a new feature or
corrected a typo, all contributions are welcome. General instructions on how to
contribute can be found in the [CONTRIBUTING](CONTRIBUTING.md) file.

## Licensing Info

This code is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for
details.

## References

This package is part of the VIRL 2 Network Simulation platform. For details, go
to http://virl.cisco.com
