====
gptf
====

**gptf** is a library for building Gaussian Process models in Python using
TensorFlow_, based on GPflow_. Its benefits over
GPflow include:

- Ops can be easily pinned to devices / graphs, and inherit their device
  placement from their parents.
- Autoflow that plays nicely with the distributed runtime.
- Better trees for a better world.

Explanatory notebooks can be found in the `notebooks directory`_,
and documentation can be found here_.

.. _TensorFlow: https://www.tensorflow.org
.. _GPflow: https://github.com/GPflow/GPflow
.. _notebooks directory: notebooks
.. _here: http://icl-sml.github.io/gptf/


Installation
------------

.. code:: bash

   pip install gptf

or, from source:

.. code:: bash

   git clone https://github.com/ICL-SML/gptf
   cd gptf
   pip install .


Running tests
-------------

.. code:: bash

  git clone https://github.com/ICL-SML/gptf
  cd gptf
  pip install nose
  nosetests

