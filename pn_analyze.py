import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import _data
import _graphs

REGEX_PATTERN_GCI = r'[A-Z]\w{5,7}'
TIMESTAMP_PARSE_DICT = {'case_timestamp': '%Y-%m-%dT%H:%M:%S.%fZ'}


def load_up_initial_db(sql_table, disk_engine, date_fmt):
    # param date_fmt dict like in read_sql_table
    df_tot = []
    for chunk in pd.read_sql_table(sql_table, disk_engine, chunksize=1000, parse_dates=date_fmt):
        df_tot.append(chunk)
    metrics = pd.concat(df_tot)
    return metrics


# def strict_startup(table):
#     dataframe = load_up_initial_db(table, disk_engine)
#     prune(dataframe)
#     deleted_runs, dataframe = remove_totally_failed_tests(dataframe)
#     return dataframe


class AnyData:
    def __init__(self, disk_engine, table):
        self.disk_engine = disk_engine
        self.table = table
        self.df = None

    def load_up_initial_db(self, date_dict):
        df_tot = []
        for chunk in pd.read_sql_table(self.table, self.disk_engine, chunksize=10000, parse_dates=date_dict):
            df_tot.append(chunk)
        self.df = pd.concat(df_tot)


class PynetData(AnyData):
    def __init__(self, disk_engine, table):
        super().__init__(disk_engine, table)

    @property
    def now(self):
        return datetime.datetime.now()

    @property
    def latest_test_run(self):
        latest_test_run = self.df[self.df.group_uuid.isin(_data.return_guuid_latest(self.df))]
        return latest_test_run

    def load_up_initial_db(self, date_dict):
        df_tot = []
        for chunk in pd.read_sql_table(self.table, self.disk_engine, chunksize=10000, parse_dates=date_dict):
            df_tot.append(chunk)
        self.df = pd.concat(df_tot)

    def create_numeric_status(self):
        # for priming the dataframe. run @ beginning.
        boolean_map = {"passed": 1, "failed": 0, "running": 3, "skipped": 2}
        self.df['numeric_status'] = pd.Series(self.df.case_status.map(boolean_map), index=self.df.index)
        df_status = pd.get_dummies(self.df.case_status)
        self.df = pd.concat([self.df, df_status], axis=1)

    def create_date_integer(self):
        self.df['date_int'] = self.df.case_timestamp.astype(np.int64)

    def remove_totally_failed_tests(self):
        """Remove all test runs that completely failed, as they are likely garbage.
        This takes a while, should only be run on initialization of the dataframe/when appending new dataframes"""
        all_runs = self.df.group_uuid.unique()
        removed_guuids = []
        for test_run in all_runs:
            overall_status = self.df[(self.df.group_uuid == test_run) & ~_data.get_failed_mask(self.df)]
            if not len(overall_status):
                self.df = self.df[self.df.group_uuid != test_run]
                removed_guuids.append(test_run)
        return removed_guuids


class TestResult(PynetData):
    """class that represents/manipulates the data from the test_result table in the PYNET database."""
    def __init__(self, disk_engine):
        super().__init__(disk_engine, 'test_result')

    def prune(self):
        gci_bs = self.df.case_action.str.contains(REGEX_PATTERN_GCI)
        self.df = self.df[~gci_bs]

    def refresh_metrics(self, table):
        latest = self.df.case_timestamp.max()
        latest_df = pd.read_sql('select * from {0} where case_timestamp > {1}'.format(table, latest),  self.disk_engine)
        self.df = self.df.append(latest_df)

    def clean(self):
        """
            Remove any test runs that have no passing tests, they were likely garbage,
            Remove GCI crap if it exists in any endpoint (use ml later),

        """
        self.remove_totally_failed_tests()
        self.prune()

    def add_numeric_cols(self):
        """
        Create numeric via get_dummies, and one from a map (which one is more useful? idk. we'll see.)
        """
        self.create_numeric_status()
        self.create_date_integer()

    def startup(self):
        self.load_up_initial_db(TIMESTAMP_PARSE_DICT)
        self.add_numeric_cols()

    def strict_startup(self):
        self.load_up_initial_db(TIMESTAMP_PARSE_DICT)
        self.clean()
        self.add_numeric_cols()

    def plot_duration_by_endpoint(self):
        # plots all endpoints against the duration of the cases run on it. figure out how to make this a more useful
        # bar plot with median times, etc
        duration_by_end_df = pd.DataFrame({
                                            'case_endpoint': self.df.case_endpoint,
                                            'case_duration': self.df.case_duration
                                          })
        fig, ax = plt.subplots(figsize=(20,10))
        bp = duration_by_end_df.groupby('case_endpoint')
        xticks = _graphs.create_uniform_tcks(duration_by_end_df.case_endpoint)
        # print(bp.case_endpoint)
        ax.scatter(xticks, duration_by_end_df.case_duration)
        ax.set_xticklabels(duration_by_end_df.case_endpoint, rotation='vertical')
        return bp

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