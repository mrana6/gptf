try:
    from inspect import signature
except ImportError:
    # at time of writing, funcsigs does not implement apply_defaults
    from funcsigs import BoundArguments, Parameter
    def apply_defaults(self):
        for param in self.signature.parameters.values():
            if (param.name not in self.arguments and 
                    param.default is not Parameter.empty):
                self.arguments[param.name] = param.default
    BoundArguments.apply_defaults = apply_defaults
