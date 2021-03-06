import requests
import zipfile
import io
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import numpy as np

from nempy import check


def _download_to_df(url, table_name, year, month):
    """Downloads a zipped csv file and converts it to a pandas DataFrame, returns the DataFrame.

    Examples
    --------
    This will only work if you are connected to the internet.

    >>> url = ('http://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{year}/MMSDM_{year}_{month}/' +
    ...        'MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_DVD_{table}_{year}{month}010000.zip')

    >>> table_name = 'DISPATCHREGIONSUM'

    >>> df = _download_to_df(url, table_name='DISPATCHREGIONSUM', year=2020, month=1)

    >>> print(df)
           I  DISPATCH  ... SEMISCHEDULE_CLEAREDMW  SEMISCHEDULE_COMPLIANCEMW
    0      D  DISPATCH  ...              549.30600                    0.00000
    1      D  DISPATCH  ...              102.00700                    0.00000
    2      D  DISPATCH  ...              387.40700                    0.00000
    3      D  DISPATCH  ...              145.43200                    0.00000
    4      D  DISPATCH  ...              136.85200                    0.00000
    ...   ..       ...  ...                    ...                        ...
    45380  D  DISPATCH  ...              757.47600                    0.00000
    45381  D  DISPATCH  ...              142.71600                    0.00000
    45382  D  DISPATCH  ...              310.28903                    0.36103
    45383  D  DISPATCH  ...               83.94100                    0.00000
    45384  D  DISPATCH  ...              196.69610                    0.69010
    <BLANKLINE>
    [45385 rows x 109 columns]

    Parameters
    ----------
    url : str
        A url of the format 'PUBLIC_DVD_{table}_{year}{month}010000.zip', typically this will be a location on AEMO's
        nemweb portal where data is stored in monthly archives.

    table_name : str
        The name of the table you want to download from nemweb.

    year : int
        The year the table is from.

    month : int
        The month the table is form.

    Returns
    -------
    pd.DataFrame

    Raises
    ------
    MissingData
        If internet connection is down, nemweb is down or data requested is not on nemweb.

    """
    # Insert the table_name, year and month into the url.
    url = url.format(table=table_name, year=year, month=str(month).zfill(2))
    # Download the file.
    r = requests.get(url)
    if r.status_code != 200:
        raise _MissingData(("""Requested data for table: {}, year: {}, month: {} 
                              not downloaded. Please check your internet connection. Also check
                              http://nemweb.com.au/#mms-data-model, to see if your requested
                              data is uploaded.""").format(table_name, year, month))
    # Convert the contents of the response into a zipfile object.
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    # Get the name of the file inside the zip object, assuming only one file is zipped inside.
    file_name = zf.namelist()[0]
    # Read the file into a DataFrame.
    data = pd.read_csv(zf.open(file_name), skiprows=1)
    # Discard last row of DataFrame
    data = data[:-1]
    return data


class _MissingData(Exception):
    """Raise for nemweb not returning status 200 for file request."""


class _MMSTable:
    """Manages Market Management System (MMS) tables stored in an sqlite database.

    This class creates the table in the data base when the object is instantiated. Methods for adding adding and
    retrieving data are added by sub classing.
    """

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        """Creates a table in sqlite database that the connection is provided for.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = _MMSTable(table_name='a_table', table_columns=['col_1', 'col_2'], table_primary_keys=['col_1'],
        ...                  con=con)

        Clean up by deleting database created.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        table_name : str
            Name of the table.
        table_columns : list(str)
            List of table column names.
        table_primary_keys : list(str)
            Table columns to use as primary keys.
        con : sqlite3.Connection
            Connection to an existing database.
        """
        self.con = con
        self.table_name = table_name
        self.table_columns = table_columns
        self.table_primary_keys = table_primary_keys
        # url that sub classes will use to pull MMS tables from nemweb.
        self.url = 'http://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{year}/MMSDM_{year}_{month}/' + \
                   'MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_DVD_{table}_{year}{month}010000.zip'
        self.columns_types = {
            'INTERVAL_DATETIME': 'TEXT', 'DUID': 'TEXT', 'BIDTYPE': 'TEXT', 'BANDAVAIL1': 'REAL', 'BANDAVAIL2': 'REAL',
            'BANDAVAIL3': 'REAL', 'BANDAVAIL4': 'REAL', 'BANDAVAIL5': 'REAL', 'BANDAVAIL6': 'REAL',
            'BANDAVAIL7': 'REAL', 'BANDAVAIL8': 'REAL', 'BANDAVAIL9': 'REAL', 'BANDAVAIL10': 'REAL', 'MAXAVAIL': 'REAL',
            'ENABLEMENTMIN': 'REAL', 'ENABLEMENTMAX': 'REAL', 'LOWBREAKPOINT': 'REAL', 'HIGHBREAKPOINT': 'REAL',
            'SETTLEMENTDATE': 'TEXT', 'PRICEBAND1': 'REAL', 'PRICEBAND2': 'REAL', 'PRICEBAND3': 'REAL',
            'PRICEBAND4': 'REAL', 'PRICEBAND5': 'REAL', 'PRICEBAND6': 'REAL', 'PRICEBAND7': 'REAL',
            'PRICEBAND8': 'REAL', 'PRICEBAND9': 'REAL', 'PRICEBAND10': 'REAL', 'T1': 'REAL', 'T2': 'REAL',
            'T3': 'REAL', 'T4': 'REAL', 'REGIONID': 'TEXT', 'TOTALDEMAND': 'REAL', 'DEMANDFORECAST': 'REAL',
            'INITIALSUPPLY': 'REAL', 'DISPATCHMODE': 'TEXT', 'AGCSTATUS': 'TEXT', 'INITIALMW': 'REAL',
            'TOTALCLEARED': 'REAL', 'RAMPDOWNRATE': 'REAL', 'RAMPUPRATE': 'REAL', 'AVAILABILITY': 'REAL',
            'RAISEREGENABLEMENTMAX': 'REAL', 'RAISEREGENABLEMENTMIN': 'REAL', 'LOWERREGENABLEMENTMAX': 'REAL',
            'LOWERREGENABLEMENTMIN': 'REAL', 'START_DATE': 'TEXT', 'END_DATE': 'TEXT', 'DISPATCHTYPE': 'TEXT',
            'CONNECTIONPOINTID': 'TEXT', 'TRANSMISSIONLOSSFACTOR': 'REAL', 'DISTRIBUTIONLOSSFACTOR': 'REAL',
            'CONSTRAINTID': 'TEXT', 'RHS': 'REAL', 'GENCONID_EFFECTIVEDATE': 'TEXT', 'GENCONID_VERSIONNO': 'TEXT',
            'GENCONID': 'TEXT', 'EFFECTIVEDATE': 'TEXT', 'VERSIONNO': 'TEXT', 'CONSTRAINTTYPE': 'TEXT',
            'GENERICCONSTRAINTWEIGHT': 'REAL', 'FACTOR': 'REAL', 'FROMREGIONLOSSSHARE': 'REAL', 'LOSSCONSTANT': 'REAL',
            'LOSSFLOWCOEFFICIENT': 'REAL', 'IMPORTLIMIT': 'REAL', 'EXPORTLIMIT': 'REAL', 'LOSSSEGMENT': 'TEXT',
            'MWBREAKPOINT': 'REAL', 'DEMANDCOEFFICIENT': 'REAL', 'INTERCONNECTORID': 'TEXT', 'REGIONFROM': 'TEXT',
            'REGIONTO': 'TEXT', 'MWFLOW': 'REAL', 'MWLOSSES': 'REAL', 'MINIMUMLOAD': 'REAL', 'MAXCAPACITY': 'REAL',
            'SEMIDISPATCHCAP': 'REAL', 'RRP': 'REAL'
        }

    def create_table_in_sqlite_db(self):
        """Creates a table in the sqlite database that the object has a connection to.

        Note
        ----
        This method and its documentation is inherited from the _MMSTable class.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = _MMSTable(table_name='EXAMPLE', table_columns=['DUID', 'BIDTYPE'], table_primary_keys=['DUID'],
        ...                  con=con)

        Create the corresponding table in the sqlite database, note this step many not be needed if you have connected
        to an existing database.

        >>> table.create_table_in_sqlite_db()

        Now a table exists in the database, but its empty.

        >>> print(pd.read_sql("Select * from example", con=con))
        Empty DataFrame
        Columns: [DUID, BIDTYPE]
        Index: []

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        """
        with self.con:
            cur = self.con.cursor()
            cur.execute("""DROP TABLE IF EXISTS {};""".format(self.table_name))
            base_create_query = """CREATE TABLE {}({}, PRIMARY KEY ({}));"""
            columns = ','.join(['{} {}'.format(col, self.columns_types[col]) for col in self.table_columns])
            primary_keys = ','.join(['{}'.format(col) for col in self.table_primary_keys])
            create_query = base_create_query.format(self.table_name, columns, primary_keys)
            cur.execute(create_query)
            self.con.commit()


class _SingleDataSource(_MMSTable):
    """Manages downloading data from nemweb for tables where all relevant data is stored in lasted data file."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def set_data(self, year, month):
        """"Download data for the given table and time, replace any existing data.

        Note
        ----
        This method and its documentation is inherited from the _SingleDataSource class.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = _SingleDataSource(table_name='DUDETAILSUMMARY',
        ...                          table_columns=['DUID', 'START_DATE', 'CONNECTIONPOINTID', 'REGIONID'],
        ...                          table_primary_keys=['START_DATE', 'DUID'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Downloading data from http://nemweb.com.au/#mms-data-model into the table.

        >>> table.set_data(year=2020, month=1)

        Now the database should contain data for this table that is up to date as the end of Janurary.

        >>> query = "Select * from DUDETAILSUMMARY order by START_DATE DESC limit 1;"

        >>> print(pd.read_sql_query(query, con=con))
              DUID           START_DATE CONNECTIONPOINTID REGIONID
        0  URANQ11  2020/02/04 00:00:00            NURQ1U     NSW1

        However if we subsequently set data from a previous date then any existing data will be replaced. Note the
        change in the most recent record in the data set below.

        >>> table.set_data(year=2019, month=1)

        >>> print(pd.read_sql_query(query, con=con))
               DUID           START_DATE CONNECTIONPOINTID REGIONID
        0  WEMENSF1  2019/03/04 00:00:00            VWES2W     VIC1

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        year : int
            The year to download data for.
        month : int
            The month to download data for.

        Return
        ------
        None
        """
        data = _download_to_df(self.url, self.table_name, year, month)
        data = data.loc[:, self.table_columns]
        with self.con:
            data.to_sql(self.table_name, con=self.con, if_exists='replace', index=False)
            self.con.commit()


class _MultiDataSource(_MMSTable):
    """Manages downloading data from nemweb for tables where data main be stored across multiple monthly files."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def add_data(self, year, month):
        """"Download data for the given table and time, appends to any existing data.

        Note
        ----
        This method and its documentation is inherited from the _MultiDataSource class.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = _MultiDataSource(table_name='DISPATCHLOAD',
        ...                          table_columns=['SETTLEMENTDATE', 'DUID',  'RAMPDOWNRATE', 'RAMPUPRATE'],
        ...                          table_primary_keys=['SETTLEMENTDATE', 'DUID'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Downloading data from http://nemweb.com.au/#mms-data-model into the table.

        >>> table.add_data(year=2020, month=1)

        Now the database should contain data for this table that is up to date as the end of Janurary.

        >>> query = "Select * from DISPATCHLOAD order by SETTLEMENTDATE DESC limit 1;"

        >>> print(pd.read_sql_query(query, con=con))
                SETTLEMENTDATE   DUID  RAMPDOWNRATE  RAMPUPRATE
        0  2020/02/01 00:00:00  YWPS4         180.0       180.0

        If we subsequently add data from an earlier month the old data remains in the table, in addition to the new
        data.

        >>> table.add_data(year=2019, month=1)

        >>> print(pd.read_sql_query(query, con=con))
                SETTLEMENTDATE   DUID  RAMPDOWNRATE  RAMPUPRATE
        0  2020/02/01 00:00:00  YWPS4         180.0       180.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        year : int
            The year to download data for.
        month : int
            The month to download data for.

        Return
        ------
        None
        """
        data = _download_to_df(self.url, self.table_name, year, month)
        if 'INTERVENTION' in data.columns:
            data = data[data['INTERVENTION'] == 0]
        data = data.loc[:, self.table_columns]
        with self.con:
            data.to_sql(self.table_name, con=self.con, if_exists='append', index=False)
            self.con.commit()


class InputsBySettlementDate(_MultiDataSource):
    """Manages retrieving dispatch inputs by SETTLEMENTDATE."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time e.g. 2019/01/01 11:55:00"

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsBySettlementDate(table_name='EXAMPLE', table_columns=['SETTLEMENTDATE', 'INITIALMW'],
        ...                                table_primary_keys=['SETTLEMENTDATE'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the add_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'SETTLEMENTDATE': ['2019/01/01 11:55:00', '2019/01/01 12:00:00'],
        ...   'INITIALMW': [1.0, 2.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by SETTLEMENTDATE.

        >>> print(table.get_data(date_time='2019/01/01 12:00:00'))
                SETTLEMENTDATE  INITIALMW
        0  2019/01/01 12:00:00        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame

        """
        query = "Select * from {table} where SETTLEMENTDATE == '{datetime}'"
        query = query.format(table=self.table_name, datetime=date_time)
        return pd.read_sql_query(query, con=self.con)


class InputsByIntervalDateTime(_MultiDataSource):
    """Manages retrieving dispatch inputs by INTERVAL_DATETIME."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time e.g. 2019/01/01 11:55:00"

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsByIntervalDateTime(table_name='EXAMPLE', table_columns=['INTERVAL_DATETIME', 'INITIALMW'],
        ...                                  table_primary_keys=['INTERVAL_DATETIME'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the add_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'INTERVAL_DATETIME': ['2019/01/01 11:55:00', '2019/01/01 12:00:00'],
        ...   'INITIALMW': [1.0, 2.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by INTERVAL_DATETIME.

        >>> print(table.get_data(date_time='2019/01/01 12:00:00'))
             INTERVAL_DATETIME  INITIALMW
        0  2019/01/01 12:00:00        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame

        """
        query = "Select * from {table} where INTERVAL_DATETIME == '{datetime}'"
        query = query.format(table=self.table_name, datetime=date_time)
        return pd.read_sql_query(query, con=self.con)


class InputsByDay(_MultiDataSource):
    """Manages retrieving dispatch inputs by SETTLEMENTDATE, where inputs are stored on a daily basis."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time e.g. 2019/01/01 11:55:00, where inputs are stored on daily basis.

        Note that a market day begins with the first 5 min interval as 04:05:00, there for if and input date_time of
        2019/01/01 04:05:00 is given inputs where the SETTLEMENDATE is 2019/01/01 00:00:00 will be retrieved and if
        a date_time of 2019/01/01 04:00:00 or earlier is given then inputs where the SETTLEMENDATE is
        2018/12/31 00:00:00 will be retrieved.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsByDay(table_name='EXAMPLE', table_columns=['SETTLEMENTDATE', 'INITIALMW'],
        ...                     table_primary_keys=['SETTLEMENTDATE'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the add_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'SETTLEMENTDATE': ['2019/01/01 00:00:00', '2019/01/02 00:00:00'],
        ...   'INITIALMW': [1.0, 2.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by SETTLEMENTDATE and the results from the appropriate market
        day starting at 04:05:00 are retrieved. In the results below note when the output changes

        >>> print(table.get_data(date_time='2019/01/01 12:00:00'))
                SETTLEMENTDATE  INITIALMW
        0  2019/01/01 00:00:00        1.0

        >>> print(table.get_data(date_time='2019/01/02 04:00:00'))
                SETTLEMENTDATE  INITIALMW
        0  2019/01/01 00:00:00        1.0

        >>> print(table.get_data(date_time='2019/01/02 04:05:00'))
                SETTLEMENTDATE  INITIALMW
        0  2019/01/02 00:00:00        2.0

        >>> print(table.get_data(date_time='2019/01/02 12:00:00'))
                SETTLEMENTDATE  INITIALMW
        0  2019/01/02 00:00:00        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame
        """

        # Convert to datetime object
        date_time = datetime.strptime(date_time, '%Y/%m/%d %H:%M:%S')
        # Change date_time provided so any time less than 04:05:00 will have the previous days date.
        date_time = date_time - timedelta(hours=4, seconds=1)
        # Convert back to string.
        date_time = datetime.isoformat(date_time).replace('-', '/').replace('T', ' ')
        # Remove the time component.
        date_time = date_time[:10]
        date_padding = ' 00:00:00'
        date_time = date_time + date_padding
        query = "Select * from {table} where SETTLEMENTDATE == '{datetime}'"
        query = query.format(table=self.table_name, datetime=date_time)
        return pd.read_sql_query(query, con=self.con)


class InputsStartAndEnd(_SingleDataSource):
    """Manages retrieving dispatch inputs by START_DATE and END_DATE."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time by START_DATE and END_DATE.

        Records with a START_DATE before or equal to the date_times and an END_DATE after the date_time will be
        returned.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsStartAndEnd(table_name='EXAMPLE', table_columns=['START_DATE', 'END_DATE', 'INITIALMW'],
        ...                           table_primary_keys=['START_DATE'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the add_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'START_DATE': ['2019/01/01 00:00:00', '2019/01/02 00:00:00'],
        ...   'END_DATE': ['2019/01/02 00:00:00', '2019/01/03 00:00:00'],
        ...   'INITIALMW': [1.0, 2.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by START_DATE and END_DATE.

        >>> print(table.get_data(date_time='2019/01/01 00:00:00'))
                    START_DATE             END_DATE  INITIALMW
        0  2019/01/01 00:00:00  2019/01/02 00:00:00        1.0

        >>> print(table.get_data(date_time='2019/01/01 12:00:00'))
                    START_DATE             END_DATE  INITIALMW
        0  2019/01/01 00:00:00  2019/01/02 00:00:00        1.0

        >>> print(table.get_data(date_time='2019/01/02 00:00:00'))
                    START_DATE             END_DATE  INITIALMW
        0  2019/01/02 00:00:00  2019/01/03 00:00:00        2.0

        >>> print(table.get_data(date_time='2019/01/02 00:12:00'))
                    START_DATE             END_DATE  INITIALMW
        0  2019/01/02 00:00:00  2019/01/03 00:00:00        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame
        """

        query = "Select * from {table} where START_DATE <= '{datetime}' and END_DATE > '{datetime}'"
        query = query.format(table=self.table_name, datetime=date_time)
        return pd.read_sql_query(query, con=self.con)


class InputsByMatchDispatchConstraints(_SingleDataSource):
    """Manages retrieving dispatch inputs by matching against the DISPATCHCONSTRAINTS table"""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time by matching against the DISPATCHCONSTRAINT table.

        First the DISPATCHCONSTRAINT table is filtered by SETTLEMENTDATE and then the contents of the classes table
        is matched against that.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsByMatchDispatchConstraints(table_name='EXAMPLE',
        ...                           table_columns=['GENCONID', 'EFFECTIVEDATE', 'VERSIONNO', 'RHS'],
        ...                           table_primary_keys=['GENCONID', 'EFFECTIVEDATE', 'VERSIONNO'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the set_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'GENCONID': ['X', 'X', 'Y', 'Y'],
        ...   'EFFECTIVEDATE': ['2019/01/02 00:00:00', '2019/01/03 00:00:00', '2019/01/01 00:00:00',
        ...                     '2019/01/03 00:00:00'],
        ...   'VERSIONNO': [1, 2, 2, 3],
        ...   'RHS': [1.0, 2.0, 2.0, 3.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        >>> data = pd.DataFrame({
        ...   'SETTLEMENTDATE' : ['2019/01/02 00:00:00', '2019/01/02 00:00:00', '2019/01/03 00:00:00',
        ...                       '2019/01/03 00:00:00'],
        ...   'CONSTRAINTID': ['X', 'Y', 'X', 'Y'],
        ...   'GENCONID_EFFECTIVEDATE': ['2019/01/02 00:00:00', '2019/01/01 00:00:00', '2019/01/03 00:00:00',
        ...                              '2019/01/03 00:00:00'],
        ...   'GENCONID_VERSIONNO': [1, 2, 2, 3]})

        >>> data.to_sql('DISPATCHCONSTRAINT', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by the contents of DISPATCHCONSTRAINT.

        >>> print(table.get_data(date_time='2019/01/02 00:00:00'))
          GENCONID        EFFECTIVEDATE VERSIONNO  RHS
        0        X  2019/01/02 00:00:00         1  1.0
        1        Y  2019/01/01 00:00:00         2  2.0

        >>> print(table.get_data(date_time='2019/01/03 00:00:00'))
          GENCONID        EFFECTIVEDATE VERSIONNO  RHS
        0        X  2019/01/03 00:00:00         2  2.0
        1        Y  2019/01/03 00:00:00         3  3.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame
        """
        columns = ','.join(['{}'.format(col) for col in self.table_columns])
        query = """Select {columns} from (
                        {table} 
                    inner join 
                        (Select * from DISPATCHCONSTRAINT where SETTLEMENTDATE == '{datetime}')
                    on GENCONID == CONSTRAINTID
                    and EFFECTIVEDATE == GENCONID_EFFECTIVEDATE
                    and VERSIONNO == GENCONID_VERSIONNO);"""
        query = query.format(columns=columns, table=self.table_name, datetime=date_time)
        return pd.read_sql_query(query, con=self.con)


class InputsByEffectiveDateVersionNoAndDispatchInterconnector(_SingleDataSource):
    """Manages retrieving dispatch inputs by EFFECTTIVEDATE and VERSIONNO."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time by EFFECTTIVEDATE and VERSIONNO.

        For each unique record (by the remaining primary keys, not including EFFECTTIVEDATE and VERSIONNO) the record
        with the most recent EFFECTIVEDATE

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsByEffectiveDateVersionNoAndDispatchInterconnector(table_name='EXAMPLE',
        ...                           table_columns=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO', 'INITIALMW'],
        ...                           table_primary_keys=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the set_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'INTERCONNECTORID': ['X', 'X', 'Y', 'Y'],
        ...   'EFFECTIVEDATE': ['2019/01/02 00:00:00', '2019/01/03 00:00:00', '2019/01/01 00:00:00',
        ...                     '2019/01/03 00:00:00'],
        ...   'VERSIONNO': [1, 2, 2, 3],
        ...   'INITIALMW': [1.0, 2.0, 2.0, 3.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        We also need to add data to DISPATCHINTERCONNECTORRES because the results of the get_data method are filtered
        against this table

        >>> data = pd.DataFrame({
        ...   'INTERCONNECTORID': ['X', 'X', 'Y'],
        ...   'SETTLEMENTDATE': ['2019/01/02 00:00:00', '2019/01/03 00:00:00', '2019/01/02 00:00:00']})

        >>> data.to_sql('DISPATCHINTERCONNECTORRES', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by the contents of DISPATCHCONSTRAINT.

        >>> print(table.get_data(date_time='2019/01/02 00:00:00'))
          INTERCONNECTORID        EFFECTIVEDATE VERSIONNO  INITIALMW
        0                X  2019/01/02 00:00:00         1        1.0
        1                Y  2019/01/01 00:00:00         2        2.0

        In the next interval interconnector Y is not present in DISPATCHINTERCONNECTORRES.

        >>> print(table.get_data(date_time='2019/01/03 00:00:00'))
          INTERCONNECTORID        EFFECTIVEDATE VERSIONNO  INITIALMW
        0                X  2019/01/03 00:00:00         2        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame
        """
        id_columns = ','.join([col for col in self.table_primary_keys if col not in ['EFFECTIVEDATE', 'VERSIONNO']])
        return_columns = ','.join(self.table_columns)
        with self.con:
            cur = self.con.cursor()
            cur.execute("DROP TABLE IF EXISTS temp;")
            cur.execute("DROP TABLE IF EXISTS temp2;")
            cur.execute("DROP TABLE IF EXISTS temp3;")
            cur.execute("DROP TABLE IF EXISTS temp4;")
            # Store just the unique sets of ids that came into effect before the the datetime in a temporary table.
            query = """CREATE TEMPORARY TABLE temp AS 
                              SELECT * 
                                FROM {table} 
                               WHERE EFFECTIVEDATE <= '{datetime}';"""
            cur.execute(query.format(table=self.table_name, datetime=date_time))
            # For each unique set of ids and effective dates get the latest versionno and sore in temporary table.
            query = """CREATE TEMPORARY TABLE temp2 AS
                              SELECT {id}, EFFECTIVEDATE, MAX(VERSIONNO) AS VERSIONNO
                                FROM temp
                               GROUP BY {id}, EFFECTIVEDATE;"""
            cur.execute(query.format(id=id_columns))
            # For each unique set of ids get the record with the most recent effective date.
            query = """CREATE TEMPORARY TABLE temp3 as
                              SELECT {id}, VERSIONNO, max(EFFECTIVEDATE) as EFFECTIVEDATE
                                FROM temp2
                               GROUP BY {id};"""
            cur.execute(query.format(id=id_columns))
            # Inner join the original table to the set of most recent effective dates and version no.
            query = """CREATE TEMPORARY TABLE temp4 AS
                              SELECT * 
                                FROM {table} 
                                     INNER JOIN temp3 
                                     USING ({id}, VERSIONNO, EFFECTIVEDATE);"""
            cur.execute(query.format(table=self.table_name, id=id_columns))
        # Inner join the most recent data with the interconnectors used in the actual interval of interest.
        query = """SELECT {cols} 
                     FROM temp4 
                          INNER JOIN (SELECT * 
                                        FROM DISPATCHINTERCONNECTORRES 
                                       WHERE SETTLEMENTDATE == '{datetime}') 
                          USING (INTERCONNECTORID);"""
        query = query.format(datetime=date_time, id=id_columns, cols=return_columns)
        data = pd.read_sql_query(query, con=self.con)
        return data


class InputsByEffectiveDateVersionNo(_SingleDataSource):
    """Manages retrieving dispatch inputs by EFFECTTIVEDATE and VERSIONNO."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self, date_time):
        """Retrieves data for the specified date_time by EFFECTTIVEDATE and VERSIONNO.

        For each unique record (by the remaining primary keys, not including EFFECTTIVEDATE and VERSIONNO) the record
        with the most recent EFFECTIVEDATE

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsByEffectiveDateVersionNo(table_name='EXAMPLE',
        ...                           table_columns=['DUID', 'EFFECTIVEDATE', 'VERSIONNO', 'INITIALMW'],
        ...                           table_primary_keys=['DUID', 'EFFECTIVEDATE', 'VERSIONNO'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the set_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'DUID': ['X', 'X', 'Y', 'Y'],
        ...   'EFFECTIVEDATE': ['2019/01/02 00:00:00', '2019/01/03 00:00:00', '2019/01/01 00:00:00',
        ...                     '2019/01/03 00:00:00'],
        ...   'VERSIONNO': [1, 2, 2, 3],
        ...   'INITIALMW': [1.0, 2.0, 2.0, 3.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data the output is filtered by most recent effective date and highest version no.

        >>> print(table.get_data(date_time='2019/01/02 00:00:00'))
          DUID        EFFECTIVEDATE VERSIONNO  INITIALMW
        0    X  2019/01/02 00:00:00         1        1.0
        1    Y  2019/01/01 00:00:00         2        2.0

        In the next interval interconnector Y is not present in DISPATCHINTERCONNECTORRES.

        >>> print(table.get_data(date_time='2019/01/03 00:00:00'))
          DUID        EFFECTIVEDATE VERSIONNO  INITIALMW
        0    X  2019/01/03 00:00:00         2        2.0
        1    Y  2019/01/03 00:00:00         3        3.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Parameters
        ----------
        date_time : str
            Should be of format '%Y/%m/%d %H:%M:%S', and always a round 5 min interval e.g. 2019/01/01 11:55:00.

        Returns
        -------
        pd.DataFrame
        """
        id_columns = ','.join([col for col in self.table_primary_keys if col not in ['EFFECTIVEDATE', 'VERSIONNO']])
        return_columns = ','.join(self.table_columns)
        with self.con:
            cur = self.con.cursor()
            cur.execute("DROP TABLE IF EXISTS temp;")
            cur.execute("DROP TABLE IF EXISTS temp2;")
            cur.execute("DROP TABLE IF EXISTS temp3;")
            cur.execute("DROP TABLE IF EXISTS temp4;")
            # Store just the unique sets of ids that came into effect before the the datetime in a temporary table.
            query = """CREATE TEMPORARY TABLE temp AS 
                              SELECT * 
                                FROM {table} 
                               WHERE EFFECTIVEDATE <= '{datetime}';"""
            cur.execute(query.format(table=self.table_name, datetime=date_time))
            # For each unique set of ids and effective dates get the latest versionno and sore in temporary table.
            query = """CREATE TEMPORARY TABLE temp2 AS
                              SELECT {id}, EFFECTIVEDATE, MAX(VERSIONNO) AS VERSIONNO
                                FROM temp
                               GROUP BY {id}, EFFECTIVEDATE;"""
            cur.execute(query.format(id=id_columns))
            # For each unique set of ids get the record with the most recent effective date.
            query = """CREATE TEMPORARY TABLE temp3 as
                              SELECT {id}, VERSIONNO, max(EFFECTIVEDATE) as EFFECTIVEDATE
                                FROM temp2
                               GROUP BY {id};"""
            cur.execute(query.format(id=id_columns))
            # Inner join the original table to the set of most recent effective dates and version no.
            query = """CREATE TEMPORARY TABLE temp4 AS
                              SELECT * 
                                FROM {table} 
                                     INNER JOIN temp3 
                                     USING ({id}, VERSIONNO, EFFECTIVEDATE);"""
            cur.execute(query.format(table=self.table_name, id=id_columns))
        # Inner join the most recent data with the interconnectors used in the actual interval of interest.
        query = """SELECT {cols} FROM temp4 ;"""
        query = query.format(cols=return_columns)
        data = pd.read_sql_query(query, con=self.con)
        return data


class InputsNoFilter(_SingleDataSource):
    """Manages retrieving dispatch inputs where no filter is require."""

    def __init__(self, table_name, table_columns, table_primary_keys, con):
        _MMSTable.__init__(self, table_name, table_columns, table_primary_keys, con)

    def get_data(self):
        """Retrieves all data in the table.

        Examples
        --------
        Set up a database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the table object.

        >>> table = InputsNoFilter(table_name='EXAMPLE', table_columns=['DUID', 'INITIALMW'],
        ...                        table_primary_keys=['DUID'], con=con)

        Create the table in the database.

        >>> table.create_table_in_sqlite_db()

        Normally you would use the set_data method to add historical data, but here we will add data directly to the
        database so some simple example data can be added.

        >>> data = pd.DataFrame({
        ...   'DUID': ['X', 'Y'],
        ...   'INITIALMW': [1.0, 2.0]})

        >>> data.to_sql('EXAMPLE', con=con, if_exists='append', index=False)

        When we call get_data all data in the table is returned.

        >>> print(table.get_data())
          DUID  INITIALMW
        0    X        1.0
        1    Y        2.0

        Clean up by closing the database and deleting if its no longer needed.

        >>> con.close()
        >>> os.remove('historical_inputs.db')

        Returns
        -------
        pd.DataFrame
        """

        return pd.read_sql_query("Select * from {table}".format(table=self.table_name), con=self.con)


class DBManager:
    """Constructs and manages a sqlite database for accessing historical inputs for NEM spot market dispatch.

    Constructs a database if none exists, otherwise connects to an existing database. Specific datasets can be added
    to the database from AEMO nemweb portal and inputs can be retrieved on a 5 min dispatch interval basis.

    Examples
    --------
    Create the database or connect to an existing one.

    >>> con = sqlite3.connect('historical_inputs.db')

    Create the database manager.

    >>> historical_inputs = DBManager(con)

    Create a set of default table in the database.

    >>> historical_inputs.create_tables()

    Add data from AEMO nemweb data portal. In this case we are adding data from the table BIDDAYOFFER_D which contains
    unit's volume bids on 5 min basis, the data comes in monthly chunks.

    >>> historical_inputs.BIDDAYOFFER_D.add_data(year=2020, month=1)

    >>> historical_inputs.BIDDAYOFFER_D.add_data(year=2020, month=2)

    This table has an add_data method indicating that data provided by AEMO comes in monthly files that do not overlap.
    If you need data for multiple months then multiple add_data calls can be made.

    Data for a specific 5 min dispatch interval can then be retrieved.

    >>> print(historical_inputs.BIDDAYOFFER_D.get_data('2020/01/10 12:35:00').head())
            SETTLEMENTDATE     DUID     BIDTYPE  ...    T3   T4  MINIMUMLOAD
    0  2020/01/10 00:00:00   AGLHAL      ENERGY  ...  10.0  2.0          2.0
    1  2020/01/10 00:00:00   AGLSOM      ENERGY  ...  35.0  2.0         16.0
    2  2020/01/10 00:00:00  ANGAST1      ENERGY  ...   0.0  0.0         46.0
    3  2020/01/10 00:00:00    APD01   LOWER5MIN  ...   0.0  0.0          0.0
    4  2020/01/10 00:00:00    APD01  LOWER60SEC  ...   0.0  0.0          0.0
    <BLANKLINE>
    [5 rows x 18 columns]

    Some tables will have a set_data method instead of an add_data method, indicating that the most recent data file
    provided by AEMO contains all historical data for this table. In this case if multiple calls to the set_data method
    are made the new data replaces the old.

    >>> historical_inputs.DUDETAILSUMMARY.set_data(year=2020, month=2)

    Data for a specific 5 min dispatch interval can then be retrieved.

    >>> print(historical_inputs.DUDETAILSUMMARY.get_data('2020/01/10 12:35:00').head())
           DUID  ... DISTRIBUTIONLOSSFACTOR
    0    AGLHAL  ...                 1.0000
    1   AGLNOW1  ...                 1.0000
    2  AGLSITA1  ...                 1.0000
    3    AGLSOM  ...                 0.9891
    4   ANGAST1  ...                 0.9890
    <BLANKLINE>
    [5 rows x 8 columns]

    Parameters
    ----------
    con : sqlite3.connection


    Attributes
    ----------
    BIDPEROFFER_D : InputsByIntervalDateTime
        Unit volume bids by 5 min dispatch intervals.
    BIDDAYOFFER_D : InputsByDay
        Unit price bids by market day.
    DISPATCHREGIONSUM : InputsBySettlementDate
        Regional demand terms by 5 min dispatch intervals.
    DISPATCHLOAD : InputsBySettlementDate
        Unit operating conditions by 5 min dispatch intervals.
    DUDETAILSUMMARY : InputsStartAndEnd
        Unit information by the start and end times of when the information is applicable.
    DISPATCHCONSTRAINT : InputsBySettlementDate
        The generic constraints that were used in each 5 min interval dispatch.
    GENCONDATA : InputsByMatchDispatchConstraints
        The generic constraints information, their applicability to a particular dispatch interval is determined by
        reference to DISPATCHCONSTRAINT.
    SPDREGIONCONSTRAINT : InputsByMatchDispatchConstraints
        The regional lhs terms in generic constraints, their applicability to a particular dispatch interval is
        determined by reference to DISPATCHCONSTRAINT.
    SPDCONNECTIONPOINTCONSTRAINT : InputsByMatchDispatchConstraints
        The connection point lhs terms in generic constraints, their applicability to a particular dispatch interval is
        determined by reference to DISPATCHCONSTRAINT.
    SPDINTERCONNECTORCONSTRAINT : InputsByMatchDispatchConstraints
        The interconnector lhs terms in generic constraints, their applicability to a particular dispatch interval is
        determined by reference to DISPATCHCONSTRAINT.
    INTERCONNECTOR : InputsNoFilter
        The the regions that each interconnector links.
    INTERCONNECTORCONSTRAINT : InputsByEffectiveDateAndVersionNo
        Interconnector properties FROMREGIONLOSSSHARE, LOSSCONSTANT, LOSSFLOWCOEFFICIENT, MAXMWIN, MAXMWOUT by
        EFFECTIVEDATE and VERSIONNO.
    LOSSMODEL : InputsByEffectiveDateAndVersionNo
        Break points used in linearly interpolating interconnector loss funtctions by EFFECTIVEDATE and VERSIONNO.
    LOSSFACTORMODEL : InputsByEffectiveDateAndVersionNo
        Coefficients of demand terms in interconnector loss functions.
    DISPATCHINTERCONNECTORRES : InputsBySettlementDate
        Record of which interconnector were used in a particular dispatch interval.

    """

    def __init__(self, connection):
        self.con = connection
        self.BIDPEROFFER_D = InputsByIntervalDateTime(
            table_name='BIDPEROFFER_D', table_columns=['INTERVAL_DATETIME', 'DUID', 'BIDTYPE', 'BANDAVAIL1',
                                                       'BANDAVAIL2', 'BANDAVAIL3', 'BANDAVAIL4', 'BANDAVAIL5',
                                                       'BANDAVAIL6', 'BANDAVAIL7', 'BANDAVAIL8', 'BANDAVAIL9',
                                                       'BANDAVAIL10', 'MAXAVAIL', 'ENABLEMENTMIN', 'ENABLEMENTMAX',
                                                       'LOWBREAKPOINT', 'HIGHBREAKPOINT'],
            table_primary_keys=['INTERVAL_DATETIME', 'DUID', 'BIDTYPE'], con=self.con)
        self.BIDDAYOFFER_D = InputsByDay(
            table_name='BIDDAYOFFER_D', table_columns=['SETTLEMENTDATE', 'DUID', 'BIDTYPE', 'PRICEBAND1', 'PRICEBAND2',
                                                       'PRICEBAND3', 'PRICEBAND4', 'PRICEBAND5', 'PRICEBAND6',
                                                       'PRICEBAND7', 'PRICEBAND8', 'PRICEBAND9', 'PRICEBAND10', 'T1',
                                                       'T2', 'T3', 'T4', 'MINIMUMLOAD'],
            table_primary_keys=['SETTLEMENTDATE', 'DUID', 'BIDTYPE'], con=self.con)
        self.DISPATCHREGIONSUM = InputsBySettlementDate(
            table_name='DISPATCHREGIONSUM', table_columns=['SETTLEMENTDATE', 'REGIONID', 'TOTALDEMAND',
                                                           'DEMANDFORECAST', 'INITIALSUPPLY'],
            table_primary_keys=['SETTLEMENTDATE', 'REGIONID'], con=self.con)
        self.DISPATCHLOAD = InputsBySettlementDate(
            table_name='DISPATCHLOAD', table_columns=['SETTLEMENTDATE', 'DUID', 'DISPATCHMODE', 'AGCSTATUS',
                                                      'INITIALMW', 'TOTALCLEARED', 'RAMPDOWNRATE', 'RAMPUPRATE',
                                                      'AVAILABILITY', 'RAISEREGENABLEMENTMAX', 'RAISEREGENABLEMENTMIN',
                                                      'LOWERREGENABLEMENTMAX', 'LOWERREGENABLEMENTMIN',
                                                      'SEMIDISPATCHCAP'],
            table_primary_keys=['SETTLEMENTDATE', 'DUID'], con=self.con)
        self.DISPATCHPRICE = InputsBySettlementDate(
            table_name='DISPATCHPRICE', table_columns=['SETTLEMENTDATE', 'REGIONID', 'RRP'],
            table_primary_keys=['SETTLEMENTDATE', 'REGIONID'], con=self.con)
        self.DUDETAILSUMMARY = InputsStartAndEnd(
            table_name='DUDETAILSUMMARY', table_columns=['DUID', 'START_DATE', 'END_DATE', 'DISPATCHTYPE',
                                                         'CONNECTIONPOINTID', 'REGIONID', 'TRANSMISSIONLOSSFACTOR',
                                                         'DISTRIBUTIONLOSSFACTOR'],
            table_primary_keys=['START_DATE', 'DUID'], con=self.con)
        self.DUDETAIL = InputsByEffectiveDateVersionNo(
            table_name='DUDETAIL', table_columns=['DUID', 'EFFECTIVEDATE', 'VERSIONNO', 'MAXCAPACITY'],
            table_primary_keys=['DUID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.DISPATCHCONSTRAINT = InputsBySettlementDate(
            table_name='DISPATCHCONSTRAINT', table_columns=['SETTLEMENTDATE', 'CONSTRAINTID', 'RHS',
                                                            'GENCONID_EFFECTIVEDATE', 'GENCONID_VERSIONNO'],
            table_primary_keys=['SETTLEMENTDATE', 'CONSTRAINTID'], con=self.con)
        self.GENCONDATA = InputsByMatchDispatchConstraints(
            table_name='GENCONDATA', table_columns=['GENCONID', 'EFFECTIVEDATE', 'VERSIONNO', 'CONSTRAINTTYPE',
                                                    'GENERICCONSTRAINTWEIGHT'],
            table_primary_keys=['GENCONID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.SPDREGIONCONSTRAINT = InputsByMatchDispatchConstraints(
            table_name='SPDREGIONCONSTRAINT', table_columns=['REGIONID', 'EFFECTIVEDATE', 'VERSIONNO', 'GENCONID',
                                                             'BIDTYPE', 'FACTOR'],
            table_primary_keys=['REGIONID', 'GENCONID', 'EFFECTIVEDATE', 'VERSIONNO', 'BIDTYPE'], con=self.con)
        self.SPDCONNECTIONPOINTCONSTRAINT = InputsByMatchDispatchConstraints(
            table_name='SPDCONNECTIONPOINTCONSTRAINT', table_columns=['CONNECTIONPOINTID', 'EFFECTIVEDATE', 'VERSIONNO',
                                                                      'GENCONID', 'BIDTYPE', 'FACTOR'],
            table_primary_keys=['CONNECTIONPOINTID', 'GENCONID', 'EFFECTIVEDATE', 'VERSIONNO', 'BIDTYPE'], con=self.con)
        self.SPDINTERCONNECTORCONSTRAINT = InputsByMatchDispatchConstraints(
            table_name='SPDINTERCONNECTORCONSTRAINT', table_columns=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO',
                                                                     'GENCONID', 'BIDTYPE', 'FACTOR'],
            table_primary_keys=['INTERCONNECTORID', 'GENCONID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.INTERCONNECTOR = InputsNoFilter(
            table_name='INTERCONNECTOR', table_columns=['INTERCONNECTORID', 'REGIONFROM', 'REGIONTO'],
            table_primary_keys=['INTERCONNECTORID'], con=self.con)
        self.INTERCONNECTORCONSTRAINT = InputsByEffectiveDateVersionNoAndDispatchInterconnector(
            table_name='INTERCONNECTORCONSTRAINT', table_columns=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO',
                                                                  'FROMREGIONLOSSSHARE', 'LOSSCONSTANT',
                                                                  'LOSSFLOWCOEFFICIENT', 'IMPORTLIMIT', 'EXPORTLIMIT'],
            table_primary_keys=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.LOSSMODEL = InputsByEffectiveDateVersionNoAndDispatchInterconnector(
            table_name='LOSSMODEL', table_columns=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO', 'LOSSSEGMENT',
                                                   'MWBREAKPOINT'],
            table_primary_keys=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.LOSSFACTORMODEL = InputsByEffectiveDateVersionNoAndDispatchInterconnector(
            table_name='LOSSFACTORMODEL', table_columns=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO', 'REGIONID',
                                                         'DEMANDCOEFFICIENT'],
            table_primary_keys=['INTERCONNECTORID', 'EFFECTIVEDATE', 'VERSIONNO'], con=self.con)
        self.DISPATCHINTERCONNECTORRES = InputsBySettlementDate(
            table_name='DISPATCHINTERCONNECTORRES', table_columns=['INTERCONNECTORID', 'SETTLEMENTDATE', 'MWFLOW',
                                                                   'MWLOSSES'],
            table_primary_keys=['INTERCONNECTORID', 'SETTLEMENTDATE'], con=self.con)

    def create_tables(self):
        """Drops any existing default tables and creates new ones, this method is generally called a new database.

        Examples
        --------
        Create the database or connect to an existing one.

        >>> con = sqlite3.connect('historical_inputs.db')

        Create the database manager.

        >>> historical_inputs = DBManager(con)

        Create a set of default table in the database.

        >>> historical_inputs.create_tables()

        Default tables will now exist, but will be empty.

        >>> print(pd.read_sql("Select * from DISPATCHREGIONSUM", con=con))
        Empty DataFrame
        Columns: [SETTLEMENTDATE, REGIONID, TOTALDEMAND, DEMANDFORECAST, INITIALSUPPLY]
        Index: []

        If you added data and then call create_tables again then any added data will be emptied.

        >>> historical_inputs.DISPATCHREGIONSUM.add_data(year=2020, month=1)

        >>> print(pd.read_sql("Select * from DISPATCHREGIONSUM limit 3", con=con))
                SETTLEMENTDATE REGIONID  TOTALDEMAND  DEMANDFORECAST  INITIALSUPPLY
        0  2020/01/01 00:05:00     NSW1      7245.31       -26.35352     7284.32178
        1  2020/01/01 00:05:00     QLD1      6095.75       -24.29639     6129.36279
        2  2020/01/01 00:05:00      SA1      1466.53         1.47190     1452.25647

        >>> historical_inputs.create_tables()

        >>> print(pd.read_sql("Select * from DISPATCHREGIONSUM", con=con))
        Empty DataFrame
        Columns: [SETTLEMENTDATE, REGIONID, TOTALDEMAND, DEMANDFORECAST, INITIALSUPPLY]
        Index: []

        Returns
        -------
        None
        """
        for name, attribute in self.__dict__.items():
            if hasattr(attribute, 'create_table_in_sqlite_db'):
                attribute.create_table_in_sqlite_db()


def create_loss_functions(interconnector_coefficients, demand_coefficients, demand):
    """Creates a loss function for each interconnector.

    Transforms the dynamic demand dependendent interconnector loss functions into functions that only depend on
    interconnector flow. i.e takes the function f and creates g by pre-calculating the demand dependent terms.

        f(inter_flow, flow_coefficient, nsw_demand, nsw_coefficient, qld_demand, qld_coefficient) = inter_losses

    becomes

        g(inter_flow) = inter_losses

    The mathematics of the demand dependent loss functions is described in the
    :download:`Marginal Loss Factors documentation section 3 to 5  <../../docs/pdfs/Marginal Loss Factors for the 2020-21 Financial year.pdf>`.

    Examples
    --------
    >>> import pandas as pd

    Some arbitrary regional demands.

    >>> demand = pd.DataFrame({
    ...   'region': ['VIC1', 'NSW1', 'QLD1', 'SA1'],
    ...   'loss_function_demand': [6000.0 , 7000.0, 5000.0, 3000.0]})

    Loss model details from 2020 Jan NEM web LOSSFACTORMODEL file

    >>> demand_coefficients = pd.DataFrame({
    ...   'interconnector': ['NSW1-QLD1', 'NSW1-QLD1', 'VIC1-NSW1', 'VIC1-NSW1', 'VIC1-NSW1'],
    ...   'region': ['NSW1', 'QLD1', 'NSW1', 'VIC1', 'SA1'],
    ...   'demand_coefficient': [-0.00000035146, 0.000010044, 0.000021734, -0.000031523, -0.000065967]})

    Loss model details from 2020 Jan NEM web INTERCONNECTORCONSTRAINT file

    >>> interconnector_coefficients = pd.DataFrame({
    ...   'interconnector': ['NSW1-QLD1', 'VIC1-NSW1'],
    ...   'loss_constant': [0.9529, 1.0657],
    ...   'flow_coefficient': [0.00019617, 0.00017027],
    ...   'from_region_loss_share': [0.5, 0.5]})

    Create the loss functions

    >>> loss_functions = create_loss_functions(interconnector_coefficients, demand_coefficients, demand)

    Lets use one of the loss functions, first get the loss function of VIC1-NSW1 and call it g

    >>> g = loss_functions[loss_functions['interconnector'] == 'VIC1-NSW1']['loss_function'].iloc[0]

    Calculate the losses at 600 MW flow

    >>> print(g(600.0))
    -70.87199999999996

    Now for NSW1-QLD1

    >>> h = loss_functions[loss_functions['interconnector'] == 'NSW1-QLD1']['loss_function'].iloc[0]

    >>> print(h(600.0))
    35.70646799999993

    Parameters
    ----------
    interconnector_coefficients : pd.DataFrame

        ======================  ========================================================================================
        Columns:                Description:
        interconnector          unique identifier of a interconnector (as `str`)
        loss_constant           the constant term in the interconnector loss factor equation (as np.float64)
        flow_coefficient        the coefficient of the interconnector flow variable in the loss factor equation
                                (as np.float64)
        from_region_loss_share  the proportion of loss attribute to the from region, remainer are attributed to the to
                                region (as np.float64)
        ======================  ========================================================================================

    demand_coefficients : pd.DataFrame

        ==================  =========================================================================================
        Columns:            Description:
        interconnector      unique identifier of a interconnector (as `str`)
        region              the market region whose demand the coefficient applies too, required (as `str`)
        demand_coefficient  the coefficient of regional demand variable in the loss factor equation (as `np.float64`)
        ==================  =========================================================================================

    demand : pd.DataFrame

        ====================  =====================================================================================
        Columns:              Description:
        region                unique identifier of a region (as `str`)
        loss_function_demand  the estimated regional demand, as calculated by initial supply + demand forecast,
                              in MW (as `np.float64`)
        ====================  =====================================================================================

    Returns
    -------
    pd.DataFrame

        loss_functions

        ================  ============================================================================================
        Columns:          Description:
        interconnector    unique identifier of a interconnector (as `str`)
        loss_function     a `function` object that takes interconnector flow (as `float`) an input and returns
                          interconnector losses (as `float`).
        ================  ============================================================================================
    """

    demand_loss_factor_offset = pd.merge(demand_coefficients, demand, 'inner', on=['region'])
    demand_loss_factor_offset['offset'] = demand_loss_factor_offset['loss_function_demand'] * \
                                          demand_loss_factor_offset['demand_coefficient']
    demand_loss_factor_offset = demand_loss_factor_offset.groupby('interconnector', as_index=False)['offset'].sum()
    loss_functions = pd.merge(interconnector_coefficients, demand_loss_factor_offset, 'left', on=['interconnector'])
    loss_functions['loss_constant'] = loss_functions['loss_constant'] + loss_functions['offset'].fillna(0)
    loss_functions['loss_function'] = \
        loss_functions.apply(lambda x: create_function(x['loss_constant'], x['flow_coefficient']), axis=1)
    return loss_functions.loc[:, ['interconnector', 'loss_function', 'from_region_loss_share']]


def create_function(constant, flow_coefficient):
    def loss_function(flow):
        return (constant - 1) * flow + (flow_coefficient / 2) * flow ** 2

    return loss_function


def datetime_dispatch_sequence(start_time, end_time):
    """Creates a list of datetimes in the string format '%Y/%m/%d %H:%M:%S', in 5 min intervals.

    Examples
    --------

    >>> date_times = datetime_dispatch_sequence(start_time='2020/01/01 12:00:00', end_time='2020/01/01 12:20:00')

    >>> print(date_times)
    ['2020/01/01 12:05:00', '2020/01/01 12:10:00', '2020/01/01 12:15:00', '2020/01/01 12:20:00']

    Parameters
    ----------
    start_time : str
        In the datetime in the format '%Y/%m/%d %H:%M:%S' e.g. '2020/01/01 12:00:00'
    end_time : str
        In the datetime in the format '%Y/%m/%d %H:%M:%S' e.g. '2020/01/01 12:00:00'
    """
    delta = timedelta(minutes=5)
    start_time = datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S')
    date_times = []
    curr = start_time + delta
    while curr <= end_time:
        # Change the datetime object to a timestamp and modify its format by replacing characters.
        date_times.append(curr.isoformat().replace('T', ' ').replace('-', '/'))
        curr += delta
    return date_times


dispatch_type_name_map = {'GENERATOR': 'generator', 'LOAD': 'load'}


def format_unit_info(DUDETAILSUMMARY):
    """Re-formats the AEMO MSS table DUDETAILSUMMARY to be compatible with the Spot market class.

    Loss factors get combined into a single value.

    Examples
    --------

    >>> DUDETAILSUMMARY = pd.DataFrame({
    ...   'DUID': ['A', 'B'],
    ...   'DISPATCHTYPE': ['GENERATOR', 'LOAD'],
    ...   'CONNECTIONPOINTID': ['X2', 'Z30'],
    ...   'REGIONID': ['NSW1', 'SA1'],
    ...   'TRANSMISSIONLOSSFACTOR': [0.9, 0.85],
    ...   'DISTRIBUTIONLOSSFACTOR': [0.9, 0.99]})

    >>> unit_info = format_unit_info(DUDETAILSUMMARY)

    >>> print(unit_info)
      unit dispatch_type connection_point region  loss_factor
    0    A     generator               X2   NSW1       0.8100
    1    B          load              Z30    SA1       0.8415

    Parameters
    ----------
    BIDPEROFFER_D : pd.DataFrame

        ======================  =================================================================
        Columns:                Description:
        DUID                    unique identifier of a unit (as `str`)
        DISPATCHTYPE            whether the unit is GENERATOR or LOAD (as `str`)
        CONNECTIONPOINTID       the unique identifier of the units location (as `str`)
        REGIONID                the unique identifier of the units market region (as `str`)
        TRANSMISSIONLOSSFACTOR  the units loss factor at the transmission level (as `np.float64`)
        DISTRIBUTIONLOSSFACTOR  the units loss factor at the distribution level (as `np.float64`)
        ======================  =================================================================

    Returns
    ----------
    unit_info : pd.DataFrame

        ======================  ==============================================================================
        Columns:                Description:
        unit                    unique identifier of a unit (as `str`)
        dispatch_type           whether the unit is GENERATOR or LOAD (as `str`)
        connection_point        the unique identifier of the units location (as `str`)
        region                  the unique identifier of the units market region (as `str`)
        loss_factor             the units combined transmission and distribution loss factor (as `np.float64`)
        ======================  ==============================================================================
    """

    # Combine loss factors.
    DUDETAILSUMMARY['LOSSFACTOR'] = DUDETAILSUMMARY['TRANSMISSIONLOSSFACTOR'] * \
                                    DUDETAILSUMMARY['DISTRIBUTIONLOSSFACTOR']
    unit_info = DUDETAILSUMMARY.loc[:, ['DUID', 'DISPATCHTYPE', 'CONNECTIONPOINTID', 'REGIONID', 'LOSSFACTOR']]
    unit_info.columns = ['unit', 'dispatch_type', 'connection_point', 'region', 'loss_factor']
    unit_info['dispatch_type'] = unit_info['dispatch_type'].apply(lambda x: dispatch_type_name_map[x])
    return unit_info


service_name_mapping = {'ENERGY': 'energy', 'RAISEREG': 'raise_reg', 'LOWERREG': 'lower_reg', 'RAISE6SEC': 'raise_6s',
                        'RAISE60SEC': 'raise_60s', 'RAISE5MIN': 'raise_5min', 'LOWER6SEC': 'lower_6s',
                        'LOWER60SEC': 'lower_60s', 'LOWER5MIN': 'lower_5min'}


def format_volume_bids(BIDPEROFFER_D):
    """Re-formats the AEMO MSS table BIDDAYOFFER_D to be compatible with the Spot market class.

    Examples
    --------

    >>> BIDPEROFFER_D = pd.DataFrame({
    ...   'DUID': ['A', 'B'],
    ...   'BIDTYPE': ['ENERGY', 'RAISEREG'],
    ...   'BANDAVAIL1': [100.0, 50.0],
    ...   'BANDAVAIL2': [10.0, 10.0],
    ...   'BANDAVAIL3': [0.0, 0.0],
    ...   'BANDAVAIL4': [10.0, 10.0],
    ...   'BANDAVAIL5': [10.0, 10.0],
    ...   'BANDAVAIL6': [10.0, 10.0],
    ...   'BANDAVAIL7': [10.0, 10.0],
    ...   'BANDAVAIL8': [0.0, 0.0],
    ...   'BANDAVAIL9': [0.0, 0.0],
    ...   'BANDAVAIL10': [0.0, 0.0]})

    >>> volume_bids = format_volume_bids(BIDPEROFFER_D)

    >>> print(volume_bids)
      unit    service      1     2    3     4     5     6     7    8    9   10
    0    A     energy  100.0  10.0  0.0  10.0  10.0  10.0  10.0  0.0  0.0  0.0
    1    B  raise_reg   50.0  10.0  0.0  10.0  10.0  10.0  10.0  0.0  0.0  0.0

    Parameters
    ----------
    BIDPEROFFER_D : pd.DataFrame

        ===========  ====================================================
        Columns:     Description:
        DUID         unique identifier of a unit (as `str`)
        BIDTYPE      the service being provided (as `str`)
        PRICEBAND1   bid volume in the 1st band, in MW (as `np.float64`)
        PRICEBAND2   bid volume in the 2nd band, in MW (as `np.float64`)
        PRICEBAND10  bid volume in the 10th band, in MW (as `np.float64`)
        ===========  ====================================================

    Returns
    ----------
    demand_coefficients : pd.DataFrame

        ========  ================================================================
        Columns:  Description:
        unit      unique identifier of a dispatch unit (as `str`)
        service   the service being provided, optional, if missing energy assumed (as `str`)
        1         bid volume in the 1st band, in MW (as `np.float64`)
        2         bid volume in the 2nd band, in MW (as `np.float64`)
        :
        10        bid volume in the nth band, in MW (as `np.float64`)
        ========  ================================================================
    """

    volume_bids = BIDPEROFFER_D.loc[:, ['DUID', 'BIDTYPE', 'BANDAVAIL1', 'BANDAVAIL2', 'BANDAVAIL3', 'BANDAVAIL4',
                                      'BANDAVAIL5', 'BANDAVAIL6', 'BANDAVAIL7', 'BANDAVAIL8', 'BANDAVAIL9',
                                      'BANDAVAIL10']]
    volume_bids.columns = ['unit', 'service', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
    volume_bids['service'] = volume_bids['service'].apply(lambda x: service_name_mapping[x])
    return volume_bids


def format_price_bids(BIDDAYOFFER_D):
    """Re-formats the AEMO MSS table BIDDAYOFFER_D to be compatible with the Spot market class.

    Examples
    --------

    >>> BIDDAYOFFER_D = pd.DataFrame({
    ...   'DUID': ['A', 'B'],
    ...   'BIDTYPE': ['ENERGY', 'RAISEREG'],
    ...   'PRICEBAND1': [100.0, 50.0],
    ...   'PRICEBAND2': [10.0, 10.0],
    ...   'PRICEBAND3': [0.0, 0.0],
    ...   'PRICEBAND4': [10.0, 10.0],
    ...   'PRICEBAND5': [10.0, 10.0],
    ...   'PRICEBAND6': [10.0, 10.0],
    ...   'PRICEBAND7': [10.0, 10.0],
    ...   'PRICEBAND8': [0.0, 0.0],
    ...   'PRICEBAND9': [0.0, 0.0],
    ...   'PRICEBAND10': [0.0, 0.0]})

    >>> price_bids = format_price_bids(BIDDAYOFFER_D)

    >>> print(price_bids)
      unit    service      1     2    3     4     5     6     7    8    9   10
    0    A     energy  100.0  10.0  0.0  10.0  10.0  10.0  10.0  0.0  0.0  0.0
    1    B  raise_reg   50.0  10.0  0.0  10.0  10.0  10.0  10.0  0.0  0.0  0.0

    Parameters
    ----------
    BIDDAYOFFER_D : pd.DataFrame

        ===========  ====================================================
        Columns:     Description:
        DUID         unique identifier of a unit (as `str`)
        BIDTYPE      the service being provided (as `str`)
        PRICEBAND1   bid price in the 1st band, in MW (as `np.float64`)
        PRICEBAND2   bid price in the 2nd band, in MW (as `np.float64`)
        PRICEBAND10  bid price in the 10th band, in MW (as `np.float64`)
        ===========  ====================================================

    Returns
    ----------
    demand_coefficients : pd.DataFrame

        ========  ================================================================
        Columns:  Description:
        unit      unique identifier of a dispatch unit (as `str`)
        service   the service being provided, optional, if missing energy assumed (as `str`)
        1         bid price in the 1st band, in MW (as `np.float64`)
        2         bid price in the 2nd band, in MW (as `np.float64`)
        10         bid price in the nth band, in MW (as `np.float64`)
        ========  ================================================================
    """

    price_bids = BIDDAYOFFER_D.loc[:, ['DUID', 'BIDTYPE', 'PRICEBAND1', 'PRICEBAND2', 'PRICEBAND3', 'PRICEBAND4',
                                       'PRICEBAND5', 'PRICEBAND6', 'PRICEBAND7', 'PRICEBAND8', 'PRICEBAND9',
                                       'PRICEBAND10']]
    price_bids.columns = ['unit', 'service', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
    price_bids['service'] = price_bids['service'].apply(lambda x: service_name_mapping[x])
    return price_bids


def format_interconnector_definitions(INTERCONNECTOR, INTERCONNECTORCONSTRAINT):
    """Re-format and combine the AEMO MSS tables INTERCONNECTOR and INTERCONNECTORCONSTRAINT for the Spot market class.

    Examples
    --------

    >>> INTERCONNECTOR = pd.DataFrame({
    ... 'INTERCONNECTORID': ['X', 'Y'],
    ... 'REGIONFROM': ['NSW', 'VIC'],
    ... 'REGIONTO': ['QLD', 'SA']})

    >>> INTERCONNECTORCONSTRAINT = pd.DataFrame({
    ... 'INTERCONNECTORID': ['X', 'Y'],
    ... 'IMPORTLIMIT': [100.0, 900.0],
    ... 'EXPORTLIMIT': [150.0, 800.0]})

    >>> interconnector_paramaters = format_interconnector_definitions(INTERCONNECTOR, INTERCONNECTORCONSTRAINT)

    >>> print(interconnector_paramaters)
      interconnector to_region from_region    min    max
    0              X       NSW         QLD -100.0  150.0
    1              Y       VIC          SA -900.0  800.0


    Parameters
    ----------
    INTERCONNECTOR : pd.DataFrame

        ===================  ======================================================================================
        Columns:             Description:
        INTERCONNECTORID     unique identifier of a interconnector (as `str`)
        REGIONFROM           the region that power is drawn from when flow is in the positive direction (as `str`)
        REGIONTO             the region that receives power when flow is in the positive direction (as `str`)
        ===================  ======================================================================================

    INTERCONNECTORCONSTRAINT : pd.DataFrame

        ===================  ======================================================================================
        Columns:             Description:
        INTERCONNECTORID     unique identifier of a interconnector (as `str`)
        IMPORTLIMIT          the maximum power flow in the positive direction, in MW (as `np.float64`)
        EXPORTLIMIT          the maximum power flow in the negative direction, in MW (as `np.float64`)
        ===================  ======================================================================================

    Returns
    ----------
    interconnectors : pd.DataFrame

            ==============  =====================================================================================
            Columns:        Description:
            interconnector  unique identifier of a interconnector (as `str`)
            to_region       the region that receives power when flow is in the positive direction (as `str`)
            from_region     the region that power is drawn from when flow is in the positive direction (as `str`)
            max             the maximum power flow in the positive direction, in MW (as `np.float64`)
            min             the maximum power flow in the negative direction, in MW (as `np.float64`)
            ==============  =====================================================================================
    """
    interconnector_directions = INTERCONNECTOR.loc[:, ['INTERCONNECTORID', 'REGIONFROM', 'REGIONTO']]
    interconnector_directions.columns = ['interconnector', 'to_region', 'from_region']
    interconnector_paramaters = INTERCONNECTORCONSTRAINT.loc[:, ['INTERCONNECTORID', 'IMPORTLIMIT', 'EXPORTLIMIT']]
    interconnector_paramaters.columns = ['interconnector', 'min', 'max']
    interconnector_paramaters['min'] = -1 * interconnector_paramaters['min']
    interconnectors = pd.merge(interconnector_directions, interconnector_paramaters, 'inner', on='interconnector')
    return interconnectors


def format_interconnector_loss_coefficients(INTERCONNECTORCONSTRAINT):
    """Re-formats the AEMO MSS table INTERCONNECTORCONSTRAINT to be compatible with the Spot market class.

    Examples
    --------

    >>> INTERCONNECTORCONSTRAINT = pd.DataFrame({
    ... 'INTERCONNECTORID': ['X', 'Y', 'Z'],
    ... 'LOSSCONSTANT': [1.0, 1.1, 1.0],
    ... 'LOSSFLOWCOEFFICIENT': [0.001, 0.003, 0.005],
    ... 'FROMREGIONLOSSSHARE': [0.5, 0.3, 0.7,]})

    >>> interconnector_paramaters = format_interconnector_loss_coefficients(INTERCONNECTORCONSTRAINT)

    >>> print(interconnector_paramaters)
      interconnector  loss_constant  flow_coefficient  from_region_loss_share
    0              X            1.0             0.001                     0.5
    1              Y            1.1             0.003                     0.3
    2              Z            1.0             0.005                     0.7


    Parameters
    ----------
    INTERCONNECTORCONSTRAINT : pd.DataFrame

        ===================  =======================================================================================
        Columns:             Description:
        INTERCONNECTORID     unique identifier of a interconnector (as `str`)
        LOSSCONSTANT         the constant term in the interconnector loss factor equation (as np.float64)
        LOSSFLOWCOEFFICIENT  the coefficient of the interconnector flow variable in the loss factor equation (as np.float64)
        FROMREGIONLOSSSHARE  the proportion of loss attribute to the from region, remainder is attributed to the to region (as np.float64)
        ===================  =======================================================================================

    Returns
    ----------
    interconnector_paramaters : pd.DataFrame

        ======================  ========================================================================================
        Columns:                Description:
        interconnector          unique identifier of a interconnector (as `str`)
        loss_constant           the constant term in the interconnector loss factor equation (as np.float64)
        flow_coefficient        the coefficient of the interconnector flow variable in the loss factor equation (as np.float64)
        from_region_loss_share  the proportion of loss attribute to the from region, remainer are attributed to the to region (as np.float64)
        ======================  ========================================================================================
    """

    interconnector_paramaters = INTERCONNECTORCONSTRAINT.loc[:, ['INTERCONNECTORID', 'LOSSCONSTANT',
                                                                 'LOSSFLOWCOEFFICIENT', 'FROMREGIONLOSSSHARE']]
    interconnector_paramaters.columns = ['interconnector', 'loss_constant', 'flow_coefficient',
                                         'from_region_loss_share']
    return interconnector_paramaters


def format_interconnector_loss_demand_coefficient(LOSSFACTORMODEL):
    """Re-formats the AEMO MSS table LOSSFACTORMODEL to be compatible with the Spot market class.

    Examples
    --------

    >>> LOSSFACTORMODEL = pd.DataFrame({
    ... 'INTERCONNECTORID': ['X', 'X', 'X', 'Y', 'Y'],
    ... 'REGIONID': ['A', 'B', 'C', 'C', 'D'],
    ... 'DEMANDCOEFFICIENT': [0.001, 0.003, 0.005, 0.0001, 0.002]})

    >>> demand_coefficients = format_interconnector_loss_demand_coefficient(LOSSFACTORMODEL)

    >>> print(demand_coefficients)
      interconnector region  demand_coefficient
    0              X      A              0.0010
    1              X      B              0.0030
    2              X      C              0.0050
    3              Y      C              0.0001
    4              Y      D              0.0020


    Parameters
    ----------
    LOSSFACTORMODEL : pd.DataFrame

        =================  ======================================================================================
        Columns:           Description:
        INTERCONNECTORID   unique identifier of a interconnector (as `str`)
        REGIONID           unique identifier of a market region (as `str`)
        DEMANDCOEFFICIENT  the coefficient of regional demand variable in the loss factor equation (as `np.float64`)
        =================  ======================================================================================

    Returns
    ----------
    demand_coefficients : pd.DataFrame

        ==================  =========================================================================================
        Columns:            Description:
        interconnector      unique identifier of a interconnector (as `str`)
        region              the market region whose demand the coefficient applies too, required (as `str`)
        demand_coefficient  the coefficient of regional demand variable in the loss factor equation (as `np.float64`)
        ==================  =========================================================================================
    """
    demand_coefficients = LOSSFACTORMODEL.loc[:, ['INTERCONNECTORID', 'REGIONID', 'DEMANDCOEFFICIENT']]
    demand_coefficients.columns = ['interconnector', 'region', 'demand_coefficient']
    return demand_coefficients


def format_regional_demand(DISPATCHREGIONSUM):
    """Re-formats the AEMO MSS table DISPATCHREGIONSUM to be compatible with the Spot market class.

    Note the demand term used in the interconnector loss functions is calculated by summing the initial supply and the
    demand forecast.

    Examples
    --------

    >>> DISPATCHREGIONSUM = pd.DataFrame({
    ... 'REGIONID': ['NSW1', 'SA1'],
    ... 'TOTALDEMAND': [8000.0, 4000.0],
    ... 'DEMANDFORECAST': [10.0, -10.0],
    ... 'INITIALSUPPLY': [7995.0, 4006.0]})

    >>> regional_demand = format_regional_demand(DISPATCHREGIONSUM)

    >>> print(regional_demand)
      region  demand  loss_function_demand
    0   NSW1  8000.0                8005.0
    1    SA1  4000.0                3996.0

    Parameters
    ----------
    DISPATCHREGIONSUM : pd.DataFrame

        ================  ==========================================================================================
        Columns:          Description:
        REGIONID          unique identifier of a market region (as `str`)
        TOTALDEMAND       the non dispatchable demand the region, in MW (as `np.float64`)
        INITIALSUPPLY     the generation supplied in th region at the start of the interval, in MW (as `np.float64`)
        DEMANDFORECAST    the expected change in demand over dispatch interval, in MW (as `np.float64`)
        ================  ==========================================================================================

    Returns
    ----------
    regional_demand : pd.DataFrame

        ====================  ======================================================================================
        Columns:              Description:
        region                unique identifier of a market region (as `str`)
        demand                the non dispatchable demand the region, in MW (as `np.float64`)
        loss_function_demand  the measure of demand used when creating interconnector loss functions, in MW (as `np.float64`)
        ====================  ======================================================================================
    """

    DISPATCHREGIONSUM['loss_function_demand'] = DISPATCHREGIONSUM['INITIALSUPPLY'] + DISPATCHREGIONSUM['DEMANDFORECAST']
    regional_demand = DISPATCHREGIONSUM.loc[:, ['REGIONID', 'TOTALDEMAND', 'loss_function_demand']]
    regional_demand.columns = ['region', 'demand', 'loss_function_demand']
    return regional_demand


def format_interpolation_break_points(LOSSMODEL):
    """Re-formats the AEMO MSS table LOSSMODEL to be compatible with the Spot market class.

    Examples
    --------

    >>> LOSSMODEL = pd.DataFrame({
    ... 'INTERCONNECTORID': ['X', 'X', 'X', 'X', 'X'],
    ... 'LOSSSEGMENT': [1, 2, 3, 4, 5],
    ... 'MWBREAKPOINT': [-100.0, -50.0, 0.0, 50.0, 100.0]})

    >>> interpolation_break_points = format_interpolation_break_points(LOSSMODEL)

    >>> print(interpolation_break_points)
      interconnector  loss_segment  break_point
    0              X             1       -100.0
    1              X             2        -50.0
    2              X             3          0.0
    3              X             4         50.0
    4              X             5        100.0

    Parameters
    ----------
    LOSSMODEL : pd.DataFrame

        ================  ======================================================================================
        Columns:          Description:
        INTERCONNECTORID  unique identifier of a interconnector (as `str`)
        LOSSSEGMENT       unique identifier of a loss segment on an interconnector basis (as `np.int64`)
        MWBREAKPOINT      points between which the loss function will be linearly interpolated, in MW
                          (as `np.float64`)
        ================  ======================================================================================

    Returns
    ----------
    interpolation_break_points : pd.DataFrame

        ================  ======================================================================================
        Columns:          Description:
        interconnector    unique identifier of a interconnector (as `str`)
        break_point       points between which the loss function will be linearly interpolated, in MW (as `np.float64`)
        ================  ======================================================================================
    """

    interpolation_break_points = LOSSMODEL.loc[:, ['INTERCONNECTORID', 'LOSSSEGMENT', 'MWBREAKPOINT']]
    interpolation_break_points.columns = ['interconnector', 'loss_segment', 'break_point']
    interpolation_break_points['loss_segment'] = interpolation_break_points['loss_segment'].apply(np.int64)
    return interpolation_break_points


def determine_unit_limits(DISPATCHLOAD, BIDPEROFFER_D):
    """Approximates the unit limits used in historical dispatch, returns inputs compatible with the Spot market class.

    The exact method for determining unit limits in historical dispatch is not known. This function first assumes the
    limits are set by the AVAILABILITY, INITIALMW, RAMPUPRATE and RAMPDOWNRATE columns in the MMS table DISPATCHLOAD.
    Then if the historical dispatch amount recorded in TOTALCLEARED is outside these limits the limits are extended.
    This occurs in the following circumstances:

    * For units operating in fast start mode, i.e. dispatch mode not equal to 0.0, if the TOTALCLEARED is outside
      the ramp rate limits then new less restrictive ramp rates are calculated that allow the unit to ramp to the
      TOTALCLEARED amount.

    * For units operating with a SEMIDISPATCHCAP of 1.0 and an offered MAXAVAIL (from the MMS table) amount less than
      the AVAILABILITY, and a TOTALCLEARED amount less than or equal to MAXAVAIL, then MAXAVAIL is used as the upper
      capacity limit instead of TOTALCLEARED.

    * If the unit is incapable of ramping down to its capacity limit then the capacity limit is increased to the ramp
      down limit, to prevent a set of infeasible unit limits.

    From the testing conducted in the tests/historical_testing module these adjustments appear sufficient to ensure
    units can be dispatched to their TOTALCLEARED amount.

    Examples
    --------

    An example where a fast start units initial limits are too restrictive, note the non fast start unit with the same
    paramaters does not have it ramp rates adjusted.

    >>> DISPATCHLOAD = pd.DataFrame({
    ...   'DUID': ['A', 'B', 'C', 'D'],
    ...   'INITIALMW': [50.0, 50.0, 50.0, 50.0],
    ...   'AVAILABILITY': [90.0, 90.0, 90.0, 90.0],
    ...   'RAMPDOWNRATE': [120.0, 120.0, 120.0, 120.0],
    ...   'RAMPUPRATE': [120.0, 120.0, 120.0, 120.0],
    ...   'TOTALCLEARED': [80.0, 80.0, 30.0, 30.0],
    ...   'DISPATCHMODE': [1.0, 0.0, 4.0, 0.0],
    ...   'SEMIDISPATCHCAP': [0.0, 0.0, 0.0, 0.0]})

    >>> BIDPEROFFER_D = pd.DataFrame({
    ...   'DUID': ['A', 'B', 'C', 'D'],
    ...   'MAXAVAIL': [100.0, 100.0, 100.0, 100.0]})

    >>> unit_limits = determine_unit_limits(DISPATCHLOAD, BIDPEROFFER_D)

    >>> print(unit_limits)
      unit  initial_output  capacity  ramp_down_rate  ramp_up_rate
    0    A            50.0      90.0           120.0         360.0
    1    B            50.0      90.0           120.0         120.0
    2    C            50.0      90.0           240.0         120.0
    3    D            50.0      90.0           120.0         120.0

    An example with a unit operating with a SEMIDISPATCHCAP  of 1.0. Only unit A meets all the criteria for having its
    capacity adjusted from the reported AVAILABILITY value.

    >>> DISPATCHLOAD = pd.DataFrame({
    ...   'DUID': ['A', 'B', 'C', 'D'],
    ...   'INITIALMW': [50.0, 50.0, 50.0, 50.0],
    ...   'AVAILABILITY': [90.0, 90.0, 90.0, 90.0],
    ...   'RAMPDOWNRATE': [600.0, 600.0, 600.0, 600.0],
    ...   'RAMPUPRATE': [600.0, 600.0, 600.0, 600.0],
    ...   'TOTALCLEARED': [70.0, 90.0, 80.0, 70.0],
    ...   'DISPATCHMODE': [0.0, 0.0, 0.0, 0.0],
    ...   'SEMIDISPATCHCAP': [1.0, 1.0, 1.0, 0.0]})

    >>> BIDPEROFFER_D = pd.DataFrame({
    ...   'DUID': ['A', 'B', 'C', 'D'],
    ...   'MAXAVAIL': [80.0, 80.0, 100.0, 80.0]})

    >>> unit_limits = determine_unit_limits(DISPATCHLOAD, BIDPEROFFER_D)

    >>> print(unit_limits)
      unit  initial_output  capacity  ramp_down_rate  ramp_up_rate
    0    A            50.0      80.0           600.0         600.0
    1    B            50.0      90.0           600.0         600.0
    2    C            50.0      90.0           600.0         600.0
    3    D            50.0      90.0           600.0         600.0

    An example where the AVAILABILITY is lower than the ramp down limit.

    >>> DISPATCHLOAD = pd.DataFrame({
    ...   'DUID': ['A'],
    ...   'INITIALMW': [50.0],
    ...   'AVAILABILITY': [30.0],
    ...   'RAMPDOWNRATE': [120.0],
    ...   'RAMPUPRATE': [120.0],
    ...   'TOTALCLEARED': [40.0],
    ...   'DISPATCHMODE': [0.0],
    ...   'SEMIDISPATCHCAP': [0.0]})

    >>> BIDPEROFFER_D = pd.DataFrame({
    ...   'DUID': ['A'],
    ...   'MAXAVAIL': [30.0]})

    >>> unit_limits = determine_unit_limits(DISPATCHLOAD, BIDPEROFFER_D)

    >>> print(unit_limits)
      unit  initial_output  capacity  ramp_down_rate  ramp_up_rate
    0    A            50.0      40.0           120.0         120.0

    Parameters
    ----------
    DISPATCHLOAD : pd.DataFrame

        ===============  ======================================================================================
        Columns:         Description:
        DUID             unique identifier of a dispatch unit (as `str`)
        INITIALMW        the output of the unit at the start of the dispatch interval, in MW (as `np.float64`)
        AVAILABILITY     the reported maximum output of the unit for dispatch interval, in MW (as `np.float64`)
        RAMPDOWNRATE     the maximum rate at which the unit can decrease output, in MW/h (as `np.float64`)
        RAMPUPRATE       the maximum rate at which the unit can increase output, in MW/h (as `np.float64`)
        TOTALCLEARED     the dispatch target for interval, in MW (as `np.float64`)
        DISPATCHMODE     fast start operating mode, 0.0 for not in fast start mode, 1.0, 2.0, 3.0, 4.0 for in
                         fast start mode, (as `np.float64`)
        SEMIDISPATCHCAP  0.0 for not applicable, 1.0 if the semi scheduled unit output is capped by dispatch
                         target.
        ===============  ======================================================================================

    BIDPEROFFER_D : pd.DataFrame
        Should only be bids of type energy.

        ===============  ======================================================================================
        Columns:         Description:
        DUID             unique identifier of a dispatch unit (as `str`)
        MAXAVAIL         the maximum unit output as specified in the units bid, in MW (as `np.float64`)
        ===============  ======================================================================================

    Returns
    -------
    unit_limits : pd.DataFrame

        ==============  =====================================================================================
        Columns:        Description:
        unit            unique identifier of a dispatch unit (as `str`)
        initial_output  the output of the unit at the start of the dispatch interval, in MW (as `np.float64`)
        capacity        the maximum output of the unit if unconstrained by ramp rate, in MW (as `np.float64`)
        ramp_down_rate  the maximum rate at which the unit can decrease output, in MW/h (as `np.float64`)
        ramp_up_rate    the maximum rate at which the unit can increase output, in MW/h (as `np.float64`)
        ==============  =====================================================================================

    """

    # Override ramp rates for fast start units.
    ic = DISPATCHLOAD  # DISPATCHLOAD provides the initial operating conditions (ic).
    ic['RAMPMAX'] = ic['INITIALMW'] + ic['RAMPUPRATE'] * (5 / 60)
    ic['RAMPUPRATE'] = np.where((ic['TOTALCLEARED'] > ic['RAMPMAX']) & (ic['DISPATCHMODE'] != 0.0),
                                (ic['TOTALCLEARED'] - ic['INITIALMW']) * (60 / 5), ic['RAMPUPRATE'])
    ic['RAMPMIN'] = ic['INITIALMW'] - ic['RAMPDOWNRATE'] * (5 / 60)
    ic['RAMPDOWNRATE'] = np.where((ic['TOTALCLEARED'] < ic['RAMPMIN']) & (ic['DISPATCHMODE'] != 0.0),
                                  (ic['INITIALMW'] - ic['TOTALCLEARED']) * (60 / 5), ic['RAMPDOWNRATE'])

    # Override AVAILABILITY when SEMIDISPATCHCAP is 1.0
    ic = pd.merge(ic, BIDPEROFFER_D.loc[:, ['DUID', 'MAXAVAIL']], 'inner', on='DUID')
    ic['AVAILABILITY'] = np.where((ic['MAXAVAIL'] < ic['AVAILABILITY']) & (ic['SEMIDISPATCHCAP'] == 1.0) &
                                  (ic['TOTALCLEARED'] <= ic['MAXAVAIL']), ic['MAXAVAIL'],
                                  ic['AVAILABILITY'])

    # Where the availability is lower than the ramp down min set the AVAILABILITY to equal the ramp down min.
    ic['AVAILABILITY'] = np.where(ic['AVAILABILITY'] < ic['RAMPMIN'], ic['RAMPMIN'], ic['AVAILABILITY'])

    # Format for compatibility with the Spot market class.
    ic = ic.loc[:, ['DUID', 'INITIALMW', 'AVAILABILITY', 'RAMPDOWNRATE', 'RAMPUPRATE']]
    ic.columns = ['unit', 'initial_output', 'capacity', 'ramp_down_rate', 'ramp_up_rate']
    return ic
