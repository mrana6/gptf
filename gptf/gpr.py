"""GP regression with Gaussian noise."""
from builtins import super

from overrides import overrides
import tensorflow as tf

from gptf import GPModel, DataHolder, tf_method
from gptf import likelihoods, densities, meanfunctions
from gptf import tfhacks


#TODO: Write tests.
class GPR(GPModel):
    """Gaussian process regression with Gaussian noise.
    
    Attributes:
        inputs (DataHolder): The input data, size `N`x`D`. By default,
            this is set to recompile the model if the shape changes.
        values (DataHolder): The input data, size `N`x`D`. By default,
            this is set to recompile the model if the shape changes.
        kernel (gptf.kernels.Kernel): The kernel of the GP.
        meanfunc (gptf.meanfunctions.MeanFunctions): The mean function
            of the GP.
        likelihood (gptf.likelihoods.Gaussian): The likelihood of the GP

    Examples:
        >>> import numpy as np
        >>> from gptf import kernels
        >>> X = np.array([[0, 0, 0],  # a bunch of unique data points
        ...               [1, 1, 1],
        ...               [2, 2, 0],
        ...               [3, 0, 1],
        ...               [4, 1, 0],
        ...               [0, 2, 1],
        ...               [1, 0, 0],
        ...               [2, 1, 1],
        ...               [3, 2, 0],
        ...               [4, 0, 1]], dtype=np.float64)
        >>> gp = GPR(kernels.RBF(1.0, 1.0))
        >>> gp.fallback_name = "gp"
        >>> print(gp.summary(fmt='plain'))
        Parameterized object gp
        <BLANKLINE>
        Params:
            name                   | value | transform | prior
            -----------------------+-------+-----------+------
            gp.kernel.lengthscales | 1.000 | +ve (Exp) | nyi
            gp.kernel.variance     | 1.000 | +ve (Exp) | nyi
            gp.likelihood.variance | 1.000 | +ve (Exp) | nyi
        <BLANKLINE>

        To generate some sample training outputs, we'll compute a 
        sample from the prior with 2 latent functions at our
        training inputs.
        >>> Y = gp.compute_prior_samples(X, 2, 1)[0]
        
        Then we'll mess with the value of the parameters. When
        we optimise the model, they should return to `1.000`.
        >>> gp.kernel.variance = 1.5
        >>> gp.kernel.lengthscales = 0.8
        >>> gp.likelihood.variance = 1.3
        >>> gp.optimize(X, Y, disp=False)
        message: 'SciPy optimizer completed successfully.'
        success: True
              x: array([...,...,...])
        >>> print(gp.param_summary(fmt='plain'))
        name                   | value | transform | prior
        -----------------------+-------+-----------+------
        gp.kernel.lengthscales | 1.000 | +ve (Exp) | nyi
        gp.kernel.variance     | 1.000 | +ve (Exp) | nyi
        gp.likelihood.variance | 1.000 | +ve (Exp) | nyi

    """
    def __init__(self, kernel, meanfunction=meanfunctions.Zero()):
        """Initializer.

        Args:
            kernel (gptf.kernels.Kernel): The kernel.
            meanfunction (gptf.meanfunctions.MeanFunction):
                The mean function.

        """
        super().__init__()
        self.likelihood = likelihoods.Gaussian()
        self.kernel = kernel
        self.meanfunction = meanfunction
    
    @tf_method()
    @overrides
    def build_log_likelihood(self, X, Y):
        noise_variance = self.likelihood.variance.tensor
        K = self.kernel.K(X)
        # Add gaussian noise to kernel
        K += tfhacks.eye(tf.shape(X)[0], X.dtype) * noise_variance
        L = tf.cholesky(K)
        m = self.meanfunction(X)

        return densities.multivariate_normal(Y, m, L)

    @tf_method()
    @overrides
    def build_prior_mean_var(self, test_points, num_latent, full_cov=False):
        noise_var = self.likelihood.variance.tensor
        X = test_points
        fmean = self.meanfunction(X)
        fmean += tf.zeros([1, num_latent], fmean.dtype)  # broadcast mu
        if full_cov:
            fvar = self.kernel.K(X)
            fvar += tfhacks.eye(tf.shape(X)[0], X.dtype) * noise_var
            fvar = tf.tile(tf.expand_dims(fvar, 2), (1, 1, num_latent))
        else:
            fvar = self.kernel.KDiag(X)
            fvar += tf.ones((tf.shape(X)[0],), X.dtype) * noise_var
            fvar = tf.tile(tf.expand_dims(fvar, 1), (1, num_latent))
        return fmean, fvar

    @tf_method()
    @overrides
    def build_posterior_mean_var(self, X, Y, test_points, full_cov=False):
        noise_var = self.likelihood.variance.tensor
        Kx = self.kernel.K(X, test_points)
        K = self.kernel.K(X)
        K += tfhacks.eye(tf.shape(X)[0], X.dtype) * noise_var
        L = tf.cholesky(K)
        A = tf.matrix_triangular_solve(L, Kx, lower=True)
        V = tf.matrix_triangular_solve(L, Y - self.meanfunction(X))
        fmean = tf.matmul(A, V, transpose_a=True)
        fmean += self.meanfunction(test_points)
        if full_cov:
            fvar = self.kernel.K(test_points) - tf.matmul(A, A, transpose_a=1)
            fvar = tf.tile(tf.expand_dims(fvar, 2), (1, 1, tf.shape(Y)[1]))
        else:
            fvar = self.kernel.Kdiag(test_points)
            fvar -= tf.reduce_sum(tf.square(A), 0)
            fvar = tf.tile(tf.expand_dims(fvar, 1), (1, tf.shape(Y)[1]))
        return fmean, fvar
