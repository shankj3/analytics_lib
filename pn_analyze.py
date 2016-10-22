import os
import datetime
import threading

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from time import sleep
from pandas.util.testing import test_parallel

import _data
import _graphs
import helper

REGEX_PATTERN_GCI = r'[A-Z]\w{5,7}'
REGEX_PATTERN_DB_ID = r'[0-9]{15}'
TIMESTAMP_PARSE_DICT = {'case_timestamp': '%Y-%m-%dT%H:%M:%S.%fZ'}

# http://blog.thedataincubator.com/2015/09/painlessly-deploying-data-apps-with-bokeh-flask-and-heroku/


def load_up_initial_db(sql_table, disk_engine, date_fmt):
    # param date_fmt dict like in read_sql_table
    df_tot = []
    for chunk in pd.read_sql_table(sql_table, disk_engine, chunksize=1000, parse_dates=date_fmt):
        df_tot.append(chunk)
    metrics = pd.concat(df_tot)
    return metrics


def get_case_list_by_group(config):
    """given a PYNET config map, return the full case lists (including dependent groups) of each group"""
    # Identity = namedtuple('Identity', ['service', 'id'])
    groups = config.get('groups')
    full_case_lists = {}
    for group_name, group in groups.items():
        cases = group['cases']
        if group.get('dependencies'):
            for dep in group.get('dependencies'):
                dependencies_tests = groups.get(dep).get('cases')
                cases += dependencies_tests
        full_case_lists[group_name] = cases
    return full_case_lists


# def strict_startup(table):
#     dataframe = load_up_initial_db(table, disk_engine)
#     prune(dataframe)
#     deleted_runs, dataframe = remove_totally_failed_tests(dataframe)
#     return dataframe


class AnyData:
    def __init__(self, disk_engine, table):
        self.disk_engine = disk_engine
        self.table = table
        self.df = pd.DataFrame()

    # TODO: LOOK INTO DASK:: https://dask.readthedocs.io/en/latest/
    @test_parallel(num_threads=5)
    def load_up_initial_db(self, date_dict):
        df_tot = []
        for chunk in pd.read_sql_table(self.table, self.disk_engine, chunksize=10000, parse_dates=date_dict):
            df_tot.append(chunk)
        self.df = pd.concat(df_tot)

    def dump_to_csv(self, function, path, kwargs=None):
        """dump a smaller dataframe to a csv file
        I'm hoping I can use this to frequently trigger common df's to create graphs


        :param function: function to apply to df (groupby/aggregation.. basically to get valuable data)
        :param kwargs: map of keyword args to also pass to *function* (default empty)
        :param path: filepath to dump to

        """
        if not kwargs:
            kwargs = {}
        df_to_dump = function(self.df, **kwargs)
        df_to_dump.to_csv(path)


def return_date_mask(func):
    def here(name):
        return func(name)[0].case_timestamp.map(lambda x: x.month) == datetime.now().month


class PynetData(AnyData):
    def __init__(self, disk_engine, table):
        super().__init__(disk_engine, table)
        self._config_group_data = None
        self.time = datetime.datetime.now()
        self._this_month = None
        self._this_year = None
        self._today = None

    @property
    def now(self):
        return datetime.datetime.now()

    @property
    def latest_test_run(self):
        latest_test_run = self.df[self.df.group_uuid.isin(_data.return_guuid_latest(self.df))]
        return latest_test_run

    @property
    def config_group_data(self):
        return self._config_group_data

    @property
    def this_month(self):
        """mask of dataframe that corrasdfesponds to current month"""
        if self.time.month != datetime.datetime.now().month or self._this_month is None:
            self._update_time()
        return self._this_month

    @property
    def this_year(self):
        """mask of dataframe that corresponds to current year"""
        if self.time.year != datetime.datetime.now().year or self._this_year is None:
            self._update_time()
        return self._this_year

    @property
    def today(self):
        """mask of dataframe that corresponds to current day"""
        if self.time.day != datetime.datetime.now().day or self._today is None:
            self._update_time()
        return self._today

    def _update_time(self):
        """update all the masks, then reset the time so it won't do it again"""
        if self.time.year != datetime.datetime.now().year or self._this_year is None:
            self._this_year = _data.this_year(self.df, 'case_timestamp')
        if self.time.month != datetime.datetime.now().month or self._this_month is None:
            self._this_month = _data.this_month(self.df, 'case_timestamp')
        if self.time.day != datetime.datetime.now().day or self._today is None:
            self._today = _data.today(self.df, 'case_timestamp')
        self.time = datetime.datetime.now()

    def load_up_initial_db(self, date_dict):
        """
        Load a database by table into a pandas dataframe in chunks.

        Keyword argument:
        date_dict -- Map of columns : date string format to parse into type(pd.Timestamp)
        """
        df_tot = []
        for chunk in pd.read_sql_table(self.table, self.disk_engine, chunksize=10000, parse_dates=date_dict):
            df_tot.append(chunk)
        self.df = pd.concat(df_tot)

    def create_numeric_status(self):
        """To be run on startup:
        create a numeric representation of the case_status to be used for analysis
        """
        boolean_map = {"passed": 1, "failed": 0, "running": 3, "skipped": 2}
        self.df['numeric_status'] = pd.Series(self.df.case_status.map(boolean_map), index=self.df.index)
        df_status = pd.get_dummies(self.df.case_status)
        self.df = pd.concat([self.df, df_status], axis=1)

    def create_date_integer(self):
        """To be run on startup:
        Create integer representation of the case_timestamp
        """
        self.df['date_int'] = self.df.case_timestamp.astype(np.int64)


class TestResult(PynetData):
    """ class that represents/manipulates the data from the test_result table in the PYNET database."""
    def __init__(self, disk_engine, wait_interval=86400, writing_to_csv=True):
        super().__init__(disk_engine, 'test_result')
        self.is_cleaned = False
        self.wait_interval = wait_interval
        self.writing_to_csv = writing_to_csv
        self._csv_thread = None
        if self.writing_to_csv:
            self._much_dump()

    def _much_dump(self):
        # basically on instantiation of the class, you're going to be dumping valuable info to a csv for
        # the luigi pipeline to pick up. or you're going to just be dumping data for nothing. either way.
        # you gonna need it.
        print('_much_dump has been activated with {} s wait time'.format(self.wait_interval))
        while True:
            if self.df.empty:
                print('DF IS EMPTY. SLEEPING 35 S')
                # no use in trying to run anything if the dataframe doesn't exist.
                sleep(35)
                continue
            self._csv_thread = threading.Timer(self.wait_interval, self.data_dump)
            self._csv_thread.start()
            self._csv_thread.join()
            if not self.writing_to_csv:
                break

    def _terminate_dump(self):
        self._writing_to_csv = False

    def data_dump(self):
        dump_path = os.path.join(os.path.expanduser('~'), 'pynet-data', 'test-result')
        helper.direc_check(dump_path)
        # dump a bunch of specific useful datas to CSV
        # YES I'M AWARE THIS SHOULD BE BETTER
        print('DUMPING TO CSV!!!!!!!ASLDKFJASL;KDJFLK;ASDJF')
        self.dump_to_csv(_data.highest_failures_by_df_stdev,
                         os.path.join(dump_path, 'highest_failures_by_caseid_stdev.csv'),
                         {'groupby_key': 'case_id', 'sigma': 1.8})

    def refresh_metrics(self, table):
        latest = self.df.case_timestamp.max()
        latest_df = pd.read_sql('select * from {0} where case_timestamp > {1}'.format(table, latest),  self.disk_engine)
        if self.is_cleaned:
            latest_df = _data.prune(latest_df, [REGEX_PATTERN_GCI, REGEX_PATTERN_DB_ID])
            latest_df, _ = _data.remove_totally_failed_tests(latest_df)
        self.df = self.df.append(latest_df)

    def clean(self):
        """
            Remove any test runs that have no passing tests, they were likely garbage,
            Remove GCI crap if it exists in any endpoint (use ml later),

        """
        self.df = _data.prune(self.df, [REGEX_PATTERN_GCI, REGEX_PATTERN_DB_ID])
        self.df, _ = _data.remove_totally_failed_tests(self.df)
        self.is_cleaned = True

    def add_numeric_cols(self):
        """Create numeric via get_dummies,
        and one from a map (which one is more useful? idk. we'll see.)
        """
        self.create_numeric_status()
        self.create_date_integer()

    def startup(self):
        """Startup without removing failed tests or pruning the gci tests"""
        self.load_up_initial_db(TIMESTAMP_PARSE_DICT)
        self.add_numeric_cols()

    def strict_startup(self):
        """Startup with removing completely failed test runs and pruning gci tests."""
        self.load_up_initial_db(TIMESTAMP_PARSE_DICT)
        self.clean()
        self.add_numeric_cols()


    # def return_mean_duration_by_action(self, filter=None):
    #     mean_duration_by_action = {"case_duration": [], "case_action": []}
    #     removed_gcis_df = self.prune()
    #     for unique_val in removed_gcis_df.case_action.unique():
    #         mean_duration_by_action['case_action'].append(unique_val)
    #         mean_time = removed_gcis_df.case_duration[removed_gcis_df.case_action == unique_val].mean()
    #         mean_duration_by_action['case_duration'].append(mean_time)
    #     df = pd.DataFrame(mean_duration_by_action)
    #     return df

    def return_failed_by_action(self):
        # pass
        pass


class LiveExpected(PynetData):
    def __init__(self, database_location):
        super().__init__(database_location)
