def construct_apply_defaults():
    def apply_defaults(self):
        for param in self.signature.parameters.values():
            if (param.name not in self.arguments and 
                    param.default is not Parameter.empty):
                self.arguments[param.name] = param.default
    BoundArguments.apply_defaults = apply_defaults
try:
    from inspect import signature, Parameter, BoundArguments
    assert hasattr(BoundArguments, 'apply_defaults')
except ImportError:
    # at time of writing, funcsigs does not implement apply_defaults
    from funcsigs import BoundArguments, Parameter
    construct_apply_defaults()
except AssertionError:
    # no apply_defaults in python 3.4 either
    construct_apply_defaults()
