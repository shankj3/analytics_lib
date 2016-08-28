import pandas as pd


def remove_totally_failed_tests(test_result_df):
    """Remove all test runs that completely failed, as they are likely garbage.
    This takes a while, should only be run on initialization of the dataframe/when appending new dataframes"""
    all_runs = test_result_df.group_uuid.unique()
    removed_guuids = []
    for test_run in all_runs:
        overall_status = test_result_df[(test_result_df.group_uuid == test_run) & ~get_failed_mask(test_result_df)]
        if not len(overall_status):
            test_result_df = test_result_df[test_result_df.group_uuid != test_run]
            removed_guuids.append(test_run)
    return removed_guuids, test_result_df


def create_numeric_status(result_df):
    # for priming the dataframe. run @ beginning.
    boolean_map = {"passed": 1, "failed": 0, "running": 3, "skipped": 2}
    result_df['numeric_status'] = pd.Series(result_df.case_status.map(boolean_map), index=result_df.index)
    return result_df


def this_month(df, time_col):
    return df[time_col].map(lambda x: x.month) == now.month


def this_year(df, time_col):
    return df[time_col].map(lambda x: x.year) == now.year


def today(df, time_col):
    return df[time_col].map(lambda x: x.day) == now.day


def return_in_norm(df, col, sigma):
    return np.abs(df[col] - df[col].mean()) <= (sigma*df[col].std())


def make_datetime_column(dfa, timestamp_col, strip_val=None):
    if strip_val:
        dfa.good_date = dfa[timestamp_col].str.strip(strip_val)
        dfa.datetime = pd.Index(dfa.good_date.apply(pd.Timestamp))
    else:
        dfa.datetime = pd.Index(dfa[timestamp_col].apply(pd.Timestamp))
    return dfa.datetime


def get_failed_mask(dataframe):
    return (dataframe.case_status == 'failed') | ( dataframe.case_status == 'skipped')


def measure_by_case_action(dataframe, case_action_value, specific_endpoint=None):
    # case action duration over time.
    if specific_endpoint:
        dataframe = dataframe[dataframe.case_endpoint.str.contains(specific_endpoint)]
    case_action_df = dataframe[dataframe.case_action.str.contains(case_action_value)]
    return case_action_df


def endpoint_v_duration(dataframe, endpoint):
    # time series analysis of server -- mean of each test run over time.
    server_specific_dframe = dataframe[dataframe.case_endpoint.str.contains(endpoint)]
    guids = server_specific_dframe.group_uuid.unique()
    mean_duration = []
    timestamp = []
    for uid in guids:
        uid_df = dataframe[dataframe.group_uuid == uid]
        mean_duration.append(uid_df.case_duration.mean())
        timestamp.append(uid_df.iloc[0].case_timestamp)
    return mean_duration, timestamp


def create_mean_col_from_unique_vals(dataframe, mean_col, unique_col, include=None):
    """Return a small dataframe from a different one when you want to generate a number from the average of each unique value in a different column
       :param dataframe:
       :param mean_col: column you want to get mean value of
       :type mean_col: string
       :param unique col: column name that has repeating values. function will mask the dataframe on unique values of column, then save the mean of each of those masks
       :type unique_col: string
       :param include: optional: column to include along with mean and unique values, if those values are unique as well

       :return: dictionary of unique values and the mean of mean_col's values
       :rtype: dict
    """
    mean_col_by_unique_col = {mean_col: [], unique_col: [], 'index': []}
    ind = 0
    if include:
        mean_col_by_unique_col[include] = []
    for unique_val in dataframe[unique_col].unique():
        if include:
            included_value = dataframe[include][dataframe[unique_col] == unique_val].unique()[0]
            mean_col_by_unique_col[include].append(included_value)
        mean_col_by_unique_col[unique_col].append(unique_val)
        mean_val = dataframe[mean_col][dataframe[unique_col] == unique_val].mean()
        mean_col_by_unique_col[mean_col].append(mean_val)
        mean_col_by_unique_col['index'].append(ind)
        ind += 1
    return mean_col_by_unique_col


def normalize_series(series):
    return (series - series.mean()) / (series.max() - series.min())