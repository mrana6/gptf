# gptf

**gptf** is a library for building Gaussian Process models in Python using
[TensorFlow][tensorflow], based on [GPflow][GPflow]. Its benefits over
GPflow include:

- Ops can be easily pinned to devices / graphs, and inherit their device
  placement from their parents.
- Autoflow that plays nicely with the distributed runtime.
- Better trees for a better world.

Explanatory notebooks can be found in the [notebooks directory][notebooks],
and documentation can be found [here][documentation].

## Installation

```bash
git clone https://github.com/ICL-SML/gptf
cd gptf
pip install .
```

## Running tests

```bash
git clone https://github.com/ICL-SML/gptf
cd gptf
pip install nose
nosetests
```

[tensorflow]: https://www.tensorflow.org
[GPflow]: https://github.com/GPflow/GPflow
[notebooks]: notebooks
[documentation]: http://icl-sml.github.io/gptf/
