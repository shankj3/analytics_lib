import sqlite3
import os
import datetime
import pandas as pd
from sqlalchemy import create_engine

import expd_analytics._data as _data
import expd_analytics._graphs as _graphs


REGEX_PATTERN_GCI =  r'[A-Z]\w{5,7}'

def load_up_initial_db(sql_table, disk_engine, date_fmt):
    # param date_fmt dict like in read_sql_table
    df_tot = []
    for chunk in pd.read_sql_table(sql_table, disk_engine, chunksize=1000, parse_dates=date_fmt):
        df_tot.append(chunk)
    metrics = pd.concat(df_tot)
    return metrics


class PynetData:
    def __init__(self, database_location):
        self.database_location = database_location
        self.disk_engine = create_engine('sqlite:///%s' % self.database_location)

    @property
    def now(self):
        return datetime.datetime.now()

    def load_up_initial_db(sql_table, disk_engine):
        df_tot = []
        for chunk in pd.read_sql_table(sql_table, disk_engine, chunksize=1000):
            df_tot.append(chunk)
        self.metrics = pd.concat(df_tot)

    def pull_latest_test_run(self, dataframe):
        latest_case_mask = dataframe.case_timestamp == dataframe.case_timestamp.max()
        latest_test_run = dataframe[dataframe.group_uuid == dataframe[latest_case_mask].group_uuid.max()]
        return latest_test_run


class Metrics(PynetData):
    """class that represents/manipulates the data from the test_result table in the PYNET database."""
    def __init__(self, database_location, latest=None):
        super().__init__(database_location)
        self._latest = latest
        self.metrics = None

    @property
    def latest(self):
        latest_mask = self.metrics.case_timestamp == self.metrics.case_timestamp.max()
        latest_guuid = dataframe.group_uuid[dataframe.group_uuid == dataframe[latest_case_mask].group_uuid]
        return latest_guuid

    def pruned(self):
        # get rid of gci patterns. better way to do this?
        mask = self.metrics.case_action.str.contains(REGEX_PATTERN_GCI)
        return self.metrics[~mask]

    def refresh_metrics(self, table):
        latest = self.metrics.case_timestamp.max()
        latest_df = pd.read_sql('select * from {0} where case_timestamp > {1}'.format(table, latest))
        self.metrics = self.metrics.append(latest_df)


    def plot_duration_by_endpoint(self):
        # plots all endpoints against the duration of the cases run on it. figure out how to make this a more useful bar plot
        # with median times, etc
        duration_by_end_df = pd.DataFrame({'case_endpoint': self.metrics.case_endpoint, 'case_duration': self.metrics.case_duration})
        fig, ax = plt.subplots(figsize=(20,10))
        bp = duration_by_end_df.groupby('case_endpoint')
#         .plot.scatter(x='case_endpoint', y='case_duration', ax=ax, xticks=list(xticks_mapping['case_endpoint'].values()))
        xticks = create_uniform_tcks(duration_by_end_df.case_endpoint)
        # print(bp.case_endpoint)
        ax.scatter(xticks, duration_by_end_df.case_duration)
        ax.set_xticklabels(duration_by_end_df.case_endpoint, rotation='vertical')
        return bp

    def return_mean_duration_by_action(self, filter=None):
        mean_duration_by_action = {"case_duration": [], "case_action": []}
        removed_gcis_df = self.pruned()
        for unique_val in removed_gcis_df.case_action.unique():
            mean_duration_by_action['case_action'].append(unique_val)
            mean_time = removed_gcis_df.case_duration[removed_gcis_df.case_action == unique_val].mean()
            mean_duration_by_action['case_duration'].append(mean_time)
        df = pd.DataFrame(mean_duration_by_action)
        return df

    def return_failed_by_action(self):
        #


class LiveExpected(PynetData):
    def __init__(self, database_location):
        super().__init__(database_location)