# standard library
from builtins import super
from functools import wraps
try:  # in case of rogue Python 2.7, use contextlib2 instead of contextlib
    from contextlib import contextmanager, ExitStack
except ImportError:
    from contextlib2 import contextmanager, ExitStack

# nonstandard library
import tensorflow as tf

# local
from .trees import TreeWithCache


class ReusableContextSession(tf.Session):
    """Monkey patches `tf.Session` so that it can be reused as a context."""
    @wraps(tf.Session.__init__)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__context_manager_stack = []

    @wraps(tf.Session.__enter__)
    def __enter__(self):
        context = self.as_default()
        context.__enter__()
        self.__context_manager_stack.append(context)
        return self

    @wraps(tf.Session.__exit__)
    def __exit__(self, type_, value, traceback):
        context = self.__context_manager_stack.pop(-1)
        context.__exit__(type_, value, traceback)


class WrappedTF(TreeWithCache):
    """Provides facilities for keeping TensorFlow behind the scenes.

    WARNING: `WrappedTF` assumes that its parent, and indeed all things
    higher than it in the tree, are also `WrappedTF`. Make sure that the
    root of the tree has implemented `.get_session()`, and that
    the direct parent has implemented `.op_placement_context()`.

    Attributes:
        NO_DEVICE (object): A class-level constant, used to specify an
            empty op placement context. Do 
        tf_device (str | Callable[[tf.Operation], str] | tf.DeviceSpec
                | WrappedTF.NO_DEVICE | None):
            The device context onto which this object's ops should be pinned.
            Device contexts are applied hierarchically, starting from the
            highest parent. See `.op_placement_context()`.

            This will be passed as the sole argument to `tf.device()`. 
            `WrappedTF.NO_DEVICE` indicates that `None` will be
            passed to `tf.device`, whereas `None` indicates that `tf.device()`
            will not be called. Otherwise, see the documentation for
            `tf.device()`.

            Defaults to `None`.
        tf_graph (tf.Graph | None): The 
        tf_session_target (str | dict | None): The target under which 
            sessions should run. If this is `None`, no arguments will be 
            passed to `tf.session()`. If this is a dictionary, then its 
            contents will be used as keyword arguments for `tf.session()`. 
            Else, this will be the sole argument for
            `tf.session()`. See `.get_session()`.

    Examples:
        `op_placement_context` and `tf_method` can be used to apply
        the appropriate contexts to tensorflow methods. In the following
        
    """
    _NO_DEVICE = object()

    def __init__(self):
        super().__init__()
        self._tf_device = None
        self._tf_session_target = None
        self._tf_session = None

    # This is an attempt to guard against assignement to _NO_DEVICE
    @property
    def NO_DEVICE(self):
        return self._NO_DEVICE

    @property
    def tf_device(self):
        """Returns this object's tf_device"""
        return self._tf_device

    @tf_device.setter
    def tf_device(self, value):
        """Returns this object's tf_device"""
        self.clear_subtree_cache()
        self._tf_device = value

    @property
    def tf_session_target(self):
        return self._tf_session_target

    @tf_session_target.setter
    def tf_session_target(self, value):
        self._maybe_kill_session()
        self._tf_session_target = value

    @staticmethod
    def tf_method(method):
        """Decorator version of `op_placement_context`.
        
        Applies `instance.op_placement_context(name_scope=False)` 
        to `instance.method(...)`, and opens a name scope that matches the
        method. See examples.
        
        Examples:
            In the following example, `Example.method_a` is equivalent 
            to `Example.method_b`.
            >>> class Example(WrappedTF):
            ...     def method_a(self):
            ...         with self.op_placement_context():
            ...             with tf.name_scope(self.long_name + '.method_a/'):
            ...                 a = tf.constant(2)
            ...                 b = tf.constant(3)
            ...                 return tf.add(a, b)
            ...     @WrappedTF.tf_method
            ...     def method_b(self):
            ...         a = tf.constant(2)
            ...         b = tf.constant(3)
            ...         return tf.add(a, b)

            Devices are set properly in both methods:
            >>> e = Example()
            >>> e.tf_device = '/job:worker/task:0'
            >>> a = e.method_a()
            >>> print(a.device)
            /job:worker/task:0
            >>> b = e.method_b()
            >>> b.device == a.device
            True

            The method name is appended to the name scope!
            >>> print(a.name)
            unnamed.method_a/Add:0
            >>> print(b.name)
            unnamed.method_b/Add:0
            
        """
        @wraps(method)
        def wrapper(instance, *args, **kwargs):
            scope = "{}.{}/".format(instance.long_name, method.__name__)
            with instance.op_placement_context(), tf.name_scope(scope):
                    return method(instance, *args, **kwargs)
        return wrapper

    @contextmanager
    def op_placement_context(self, name_scope=True):
        """Applies op placement rules based on the object hierarchy.

        Examples:
            Choose the op placement context by assigning to `.tf_device`:
            >>> a, b, c, d, e = [WrappedTF() for _ in range(5)]
            >>> a.tf_device = '/job:worker'
            >>> b.tf_device = tf.DeviceSpec(device_type='GPU', device_index=0)
            >>> c.tf_device = None
            >>> d.tf_device = d.NO_DEVICE
            >>> e.tf_device = '/job:spoon'

            Device contexts are combined, starting from the context of the
            root of the tree. `c.tf_device` is `None`, so it uses the context
            of its parent.
            >>> a.child = c
            >>> with a.op_placement_context():
            ...     print(tf.constant(0).device)
            /job:worker
            >>> with c.op_placement_context():
            ...     print(tf.constant(0).device)
            /job:worker

            `d.tf_device` is `WrappedTF.NO_DEVICE`, so it resets the device
            context.
            >>> a.child = d
            >>> with d.op_placement_context():
            ...     print(tf.constant(0).device)
            <BLANKLINE>

            Other device contexts combine the way you would expect them to.
            >>> a.child = b
            >>> b.child = e
            >>> with b.op_placement_context():
            ...     # get job from a
            ...     print(tf.constant(0).device)
            /job:worker/device:GPU:0
            >>> with e.op_placement_context():
            ...     # get device from b, overwrite job from a
            ...     print(tf.constant(0).device)
            /job:spoon/device:GPU:0

            In addition, a name scope is opened that matches the object
            hierachy:
            >>> with a.op_placement_context():
            ...     print(tf.constant(0).name)
            unnamed/Const...
            >>> with b.op_placement_context():
            ...     print(tf.constant(0).name)
            unnamed.child/Const...
            >>> with e.op_placement_context():
            ...     print(tf.constant(0).name)
            unnamed.child.child/Const...

        """
        with ExitStack() as stack:
            if self.parent is not None:
                stack.enter_context(self.parent.op_placement_context())

            if self.tf_device is not None:
                dev = self.tf_device
                if dev is self.NO_DEVICE:
                    dev = None
                stack.enter_context(tf.device(dev))
            
            # enter "absolute" name scope by appending "/"
            stack.enter_context(tf.name_scope(self.long_name + "/"))

            yield

    def get_session(self):
        """Gets a TensorFlow session in which ops can be run.
        
        Returns a persistent session using the session target of the 
        highest parent.

        Returns:
            (tf.Session): A session matching the session target of the
            highest parent.

        Examples:
            Returns the same session across multiple calls:
            >>> w = WrappedTF()
            >>> sess = w.get_session()
            >>> sess is w.get_session()
            True
            >>> sess.close()
            
            >>> class Example(WrappedTF):
            ...     def op(self):
            ...         with self.op_placement_context():
            ...             return tf.constant(1)
            ...
            ...     def depth(self):
            ...         tot = 0
            ...         if self.parent is not None:
            ...             tot += self.parent.depth()
            ...         with self.get_session() as sess:
            ...             tot += sess.run(self.op())
            ...         return tot
            >>> a = Example()
            >>> a.child = Example()

            `Example` is a simple class that provides a method, `.depth()`,
            that uses TensorFlow to calculate an object's depth in the tree.
            >>> a.depth()
            1
            >>> a.child.depth()
            2

            `Example.op()` places its op based on the hierachical device 
            context. If we change `a`'s device context, we also change
            `a.child`'s.
            >>> print(a.child.op().device)
            
            >>> a.tf_device = '/job:worker/task:0'
            >>> print(a.child.op().device)
            /job:worker/task:0

            `a.child.depth()` will now result in an error:
            >>> a.child.depth()
            Traceback (most recent call last):
                ...
            tensorflow.python.framework.errors.InvalidArgumentError: ...

            `a.child.op()` is now being placed as if it were in a distributed 
            context, and the default session knows nothing about jobs or tasks.
            However, if we set `a.session_target` appropriately, 
            `a.child.get_session()` will return a session capable of
            running ops created with `a.child.op_placement_context`.
            >>> clusterdict = \\
            ...     { 'worker': ['localhost:2222']
            ...     , 'master': ['localhost:2223']
            ...     }
            >>> spec = tf.train.ClusterSpec(clusterdict)
            >>> worker = tf.train.Server(spec, job_name='worker', task_index=0)
            >>> worker.start()
            >>> master = tf.train.Server(spec, job_name='master', task_index=0)
            >>> a.tf_session_target = master.target

            `a.child.depth()` should now run smoothly.
            >>> a.child.depth()
            2

            In general, this means that as long as the session target of
            the root is set correctly, anything lower in the tree that uses
            `self.get_session()` should work without fuss.
        
        """
        if self.parent is None:
            self._maybe_create_session()
            return self._tf_session
        else:
            return self.highest_parent.get_session()

    def on_session_birth(self):
        """Called just after the session of the highest parent is created."""
        pass

    def on_session_death(self):
        """Called just before the session of the highest parent is closed."""
        pass

    def _maybe_create_session(self):
        """Handles session creation if necessary.
        
        If no session already exists, creates a session, then calls 
        `on_session_birth` for all objects lower in the tree.

        Examples:
            >>> class Example(WrappedTF):
            ...     def on_session_birth(self):
            ...         print('{}.on_session_birth called!'\
                .format(self.long_name))
            >>> w = Example()
            >>> w.child = Example()
            >>> w.child.child = Example()

            >>> w.child._maybe_create_session()
            unnamed.child.on_session_birth called!
            unnamed.child.child.on_session_birth called!
        
        """
        def new_session():
            if self.tf_session_target is None:
                return ReusableContextSession()
            elif isinstance(self.tf_session_target, dict):
                return ReusableContextSession(**self.tf_session_target)
            else:
                return ReusableContextSession(self.tf_session_target)

        if self._tf_session is None:
            self._tf_session = new_session()
            for node in self:
                node.on_session_birth()


    def _maybe_kill_session(self): 
        """Handles session destruction if necessary.

        If a session already exists, kills it then calls 
        `on_session_death` for all objects in the tree.

        Examples:
            >>> class Example(WrappedTF):
            ...     def on_session_death(self):
            ...         print('{}.on_session_death called!'\
                            .format(self.long_name))
            >>> w = Example()
            >>> w.child = Example()
            >>> w.child.child = Example()

            >>> w.child._tf_session = tf.Session()
            >>> w.child._maybe_kill_session()
            unnamed.child.on_session_death called!
            unnamed.child.child.on_session_death called!
        
        """
        if self._tf_session is not None:
            for node in self:
                node.on_session_death()
            self._tf_session.close()
            self._tf_session = None

    def __setattr__(self, name, value):
        """Deals with cache invalidations etc that happen when tree anatomy
        changes.
        
        If a `WrappedTF` acquires a new ancestor, its op placement context
        will change. When the op placement context changes, 
        """
        #TODO: this
        NotImplemented
        super().__setattr__(name, value)

    def __delattr__(self, name):
        """Deals with ca"""
        #TODO: this
        NotImplemented
        super().__delattr__(name)
