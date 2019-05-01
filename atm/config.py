from __future__ import absolute_import, unicode_literals

import argparse
import os
import re
from builtins import object, str

import yaml

from atm.constants import (
    BUDGET_TYPES, CUSTOM_CLASS_REGEX, DATA_TEST_PATH, JSON_REGEX, METHODS, METRICS, SCORE_TARGETS,
    SELECTORS, SQL_DIALECTS, TIME_FMT, TUNERS)


class Config(object):
    """
    Class which stores configuration for one aspect of ATM. Subclasses of
    Config should define the list of all configurable parameters and any
    default values for those parameters other than None (in PARAMETERS and
    DEFAULTS, respectively). The object can be initialized with any number of
    keyword arguments; only kwargs that are in PARAMETERS will be used. This
    means you can (relatively) safely do things like
        args = parser.parse_args()
        conf = Config(**vars(args))
    and only relevant parameters will be set.

    Subclasses do not need to define __init__ or any other methods.
    """
    _PREFIX = None
    _CONFIG = None

    @classmethod
    def _add_prefix(cls, name):
        if cls._PREFIX:
            return '{}_{}'.format(cls._PREFIX, name)
        else:
            return name

    @classmethod
    def _get_arg(cls, args, name):
        arg_name = cls._add_prefix(name)
        class_value = getattr(cls, name)
        if isinstance(class_value, tuple):
            default = class_value[1]
        else:
            default = None

        return args.get(arg_name, default)

    def __init__(self, args, path=None):
        if isinstance(args, argparse.Namespace):
            args = vars(args)

        config_arg = self._CONFIG or self._PREFIX
        if not path and config_arg:
            path = args.get(config_arg + '_config')

        if path:
            with open(path, 'r') as f:
                args = yaml.load(f)

        for name, value in vars(self.__class__).items():
            if not name.startswith('_') and not callable(value):
                setattr(self, name, self._get_arg(args, name))

    @classmethod
    def get_parser(cls):
        parser = argparse.ArgumentParser(add_help=False)

        if cls._PREFIX:
            parser.add_argument('--{}-config'.format(cls._PREFIX),
                                help='path to yaml {} config file'.format(cls._PREFIX))

        for name, description in vars(cls).items():
            if not name.startswith('_') and not callable(description):
                arg_name = '--' + cls._add_prefix(name).replace('_', '-')

                if isinstance(description, tuple):
                    if len(description) == 3:
                        description, default, choices = description
                        parser.add_argument(arg_name, help=description,
                                            default=default, choices=choices)
                    else:
                        description, default = description
                        if default is False:
                            parser.add_argument(arg_name, help=description,
                                                action='store_true')

                        else:
                            parser.add_argument(arg_name, help=description,
                                                default=default)

        return parser

    def to_dict(self):
        return {
            name: value
            for name, value in vars(self).items()
            if not name.startswith('_') and not callable(value)
        }

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.to_dict())


class AWSConfig(Config):
    """ Stores configuration for AWS S3 connections """
    _PREFIX = 'aws'

    access_key = 'AWS access key'
    secret_key = 'AWS secret key'
    s3_bucket = 'AWS S3 bucket to store data'
    s3_folder = 'Folder in AWS S3 bucket in which to store data'


class DatasetConfig(Config):
    """ Stores configuration of a Dataset """
    _CONFIG = 'run'

    train_path = ('Path to raw training data', os.path.join(DATA_TEST_PATH, 'pollution_1.csv'))
    test_path = 'Path to raw test data (if applicable)'
    data_description = 'Description of dataset'
    class_column = ('Name of the class column in the input data', 'class')


class SQLConfig(Config):
    """ Stores configuration for SQL database setup & connection """
    _PREFIX = 'sql'

    dialect = ('Dialect of SQL to use', 'sqlite', SQL_DIALECTS)
    database = ('Name of, or path to, SQL database', 'atm.db')
    username = 'Username for SQL database'
    password = 'Password for SQL database'
    host = 'Hostname for database machine'
    port = 'Port used to connect to database'
    query = 'Specify extra login details'


class LogConfig(Config):
    # log_level_stdout = ('minimum log level to write to stdout', 'ERROR')
    # log_level_file =('minimum log level to write to the log file', 'INFO')
    # log_dir = ('Directory where logs will be saved', 'logs')
    model_dir = ('Directory where computed models will be saved', 'models')
    metric_dir = ('Directory where model metrics will be saved', 'metrics')
    verbose_metrics = (
        'If set, compute full ROC and PR curves and '
        'per-label metrics for each classifier',
        False
    )


def option_or_path(options, regex=CUSTOM_CLASS_REGEX):
    def type_check(s):
        # first, check whether the argument is one of the preconfigured options
        if s in options:
            return s

        # otherwise, check it against the regex, and try to pull out a path to a
        # real file. The regex must extract the path to the file as groups()[0].
        match = re.match(regex, s)
        if match and os.path.isfile(match.groups()[0]):
            return s

        # if both of those fail, there's something wrong
        raise argparse.ArgumentTypeError('%s is not a valid option or path!' % s)

    return type_check


class RunConfig(Config):
    """ Stores configuration for Dataset and Datarun setup """
    _CONFIG = 'run'

    # dataset config
    # train_path = None
    # test_path = None
    # data_description = None
    # class_column = None

    # datarun config
    dataset_id = None
    methods = None
    priority = None
    budget_type = None
    budget = None
    deadline = None
    tuner = None
    r_minimum = None
    gridding = None
    selector = None
    k_window = None
    metric = None
    score_target = None

    @classmethod
    def get_parser(cls):
        parser = argparse.ArgumentParser(add_help=False)

        # make sure the text for these arguments is formatted correctly
        # this allows newlines in the help strings
        parser.formatter_class = argparse.RawTextHelpFormatter

        # Config file
        parser.add_argument('--run-config', help='path to yaml datarun config file')

        #  Dataset Arguments  #####################################################
        # ##########################################################################
        parser.add_argument('--dataset-id', type=int,
                            help="ID of dataset, if it's already in the database")

        # These are only relevant if dataset_id is not provided
        # parser.add_argument('--train-path', help='Path to raw training data',
        #                     default=os.path.join(DATA_TEST_PATH, 'pollution_1.csv'))
        # parser.add_argument('--test-path', help='Path to raw test data (if applicable)')
        # parser.add_argument('--data-description', help='Description of dataset')
        # parser.add_argument('--class-column', default='class',
        #                     help='Name of the class column in the input data')

        #   Datarun Arguments  #####################################################
        # ##########################################################################
        # Notes:
        # - Support vector machines (svm) can take a long time to train. It's not an
        #   error, it's just part of what happens when the method happens to explore
        #   a crappy set of parameters on a powerful algo like this.
        # - Stochastic gradient descent (sgd) can sometimes fail on certain
        #   parameter settings as well. Don't worry, they train SUPER fast, and the
        #   worker.py will simply log the error and continue.
        #
        # Method options:
        #   logreg - logistic regression
        #   svm    - support vector machine
        #   sgd    - linear classifier with stochastic gradient descent
        #   dt     - decision tree
        #   et     - extra trees
        #   rf     - random forest
        #   gnb    - gaussian naive bayes
        #   mnb    - multinomial naive bayes
        #   bnb    - bernoulli naive bayes
        #   gp     - gaussian process
        #   pa     - passive aggressive
        #   knn    - K nearest neighbors
        #   mlp    - multi-layer perceptron
        parser.add_argument('--methods', nargs='+',
                            type=option_or_path(METHODS, JSON_REGEX),
                            default=['logreg', 'dt', 'knn'],
                            help='Method or list of methods to use for '
                            'classification. Each method can either be one of the '
                            'pre-defined method codes listed below or a path to a '
                            'JSON file defining a custom method.'
                            '\n\nOptions: [%s]' % ', '.join(str(s) for s in METHODS))
        parser.add_argument('--priority', type=int, default=1,
                            help='Priority of the datarun (higher = more important')
        parser.add_argument('--budget-type', choices=BUDGET_TYPES, default='classifier',
                            help='Type of budget to use')
        parser.add_argument('--budget', type=int, default=100,
                            help='Value of the budget, either in classifiers or minutes')
        parser.add_argument('--deadline',
                            help='Deadline for datarun completion. If provided, this '
                            'overrides the configured walltime budget.\nFormat: {}'.format(
                                TIME_FMT.replace('%', '%%')))

        # Which field to use to judge performance, for the sake of AutoML
        # options:
        #   f1        - F1 score (harmonic mean of precision and recall)
        #   roc_auc   - area under the Receiver Operating Characteristic curve
        #   accuracy  - percent correct
        #   cohen_kappa     - measures accuracy, but controls for chance of guessing
        #                     correctly
        #   rank_accuracy   - multiclass only: percent of examples for which the true
        #                     label is in the top 1/3 most likely predicted labels
        #   ap        - average precision: nearly identical to area under
        #               precision/recall curve.
        #   mcc       - matthews correlation coefficient: good for unbalanced classes
        #
        # f1 and roc_auc may be appended with _micro or _macro to use with
        # multiclass problems.
        parser.add_argument('--metric', choices=METRICS, default='f1',
                            help='Metric by which ATM should evaluate classifiers. '
                            'The metric function specified here will be used to '
                            'compute the "judgment metric" for each classifier.')

        # Which data to use for computing judgment score
        #   cv   - cross-validated performance on training data
        #   test - performance on test data
        #   mu_sigma - lower confidence bound on cv score
        parser.add_argument('--score-target', choices=SCORE_TARGETS, default='cv',
                            help='Determines which judgment metric will be used to '
                            'search the hyperparameter space. "cv" will use the mean '
                            'cross-validated performance, "test" will use the '
                            'performance on a test dataset, and "mu_sigma" will use '
                            'the lower confidence bound on the CV performance.')

        #   AutoML Arguments  ######################################################
        # ##########################################################################
        # hyperparameter selection strategy
        # How should ATM sample hyperparameters from a given hyperpartition?
        #    uniform  - pick randomly! (baseline)
        #    gp       - vanilla Gaussian Process
        #    gp_ei    - Gaussian Process expected improvement criterion
        #    gp_eivel - Gaussian Process expected improvement, with randomness added
        #               in based on velocity of improvement
        #   path to custom tuner, defined in python
        parser.add_argument('--tuner', type=option_or_path(TUNERS), default='uniform',
                            help='Type of BTB tuner to use. Can either be one of '
                            'the pre-configured tuners listed below or a path to a '
                            'custom tuner in the form "/path/to/tuner.py:ClassName".'
                            '\n\nOptions: [%s]' % ', '.join(str(s) for s in TUNERS))

        # How should ATM select a particular hyperpartition from the set of all
        # possible hyperpartitions?
        # Options:
        #   uniform      - pick randomly
        #   ucb1         - UCB1 multi-armed bandit
        #   bestk        - MAB using only the best K runs in each hyperpartition
        #   bestkvel     - MAB with velocity of best K runs
        #   purebestkvel - always return hyperpartition with highest velocity
        #   recentk      - MAB with most recent K runs
        #   recentkvel   - MAB with velocity of most recent K runs
        #   hieralg      - hierarchical MAB: choose a classifier first, then choose
        #                  a partition
        #   path to custom selector, defined in python
        parser.add_argument('--selector', type=option_or_path(SELECTORS), default='uniform',
                            help='Type of BTB selector to use. Can either be one of '
                            'the pre-configured selectors listed below or a path to a '
                            'custom tuner in the form "/path/to/selector.py:ClassName".'
                            '\n\nOptions: [%s]' % ', '.join(str(s) for s in SELECTORS))

        # r_minimum is the number of random runs performed in each hyperpartition before
        # allowing bayesian opt to select parameters. Consult the thesis to
        # understand what those mean, but essentially:
        #
        #  if (num_classifiers_trained_in_hyperpartition >= r_minimum)
        #    # train using sample criteria
        #  else
        #    # train using uniform (baseline)
        parser.add_argument('--r-minimum', type=int, default=2,
                            help='number of random runs to perform before tuning can occur')

        # k is number that xxx-k methods use. It is similar to r_minimum, except it is
        # called k_window and determines how much "history" ATM considers for certain
        # partition selection logics.
        parser.add_argument('--k-window', type=int, default=3,
                            help='number of previous scores considered by -k selector methods')

        # gridding determines whether or not sample selection will happen on a grid.
        # If any positive integer, a grid with `gridding` points on each axis is
        # established, and hyperparameter vectors are sampled from this finite
        # space. If 0 (or blank), hyperparameters are sampled from continuous
        # space, and there is no limit to the number of hyperparameter vectors that
        # may be tried.
        parser.add_argument('--gridding', type=int, default=0,
                            help='gridding factor (0: no gridding)')

        return parser
