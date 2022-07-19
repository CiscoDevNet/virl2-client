# Minimal makefile for Sphinx documentation
# http://thomas-cokelaer.info/tutorials/sphinx/rest_syntax.html
# https://stackoverflow.com/questions/50361218/remove-the-word-module-from-sphinx-documentation/57520238#57520238
# https://stackoverflow.com/questions/21003122/sphinx-apidoc-section-titles-for-python-module-package-names#
#

# You can set these variables from the command line.
# see the top level Makefile and source/index.rst
#SPHINXOPTS    = -t internal
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile clean

clean:
	rm -rf build/* source/api/* dist

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

buildapi:
	rm -rf $(SOURCEDIR)/api/*
	sphinx-apidoc --templatedir template -fMT -o $(SOURCEDIR)/api ../virl2_client
	@echo "Auto-generation of API documentation finished. " \
	      "The generated files are in '$(SOURCEDIR)/api/'"
