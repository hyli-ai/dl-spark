import configparser
from datetime import datetime
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col, monotonically_increasing_id
from pyspark.sql.functions import year, month, dayofmonth, hour, weekofyear, date_format


config = configparser.ConfigParser()
config.read("dl.cfg")

os.environ["AWS_ACCESS_KEY_ID"]=config["AWS"]["AWS_ACCESS_KEY_ID"]
os.environ["AWS_SECRET_ACCESS_KEY"]=config["AWS"]["AWS_SECRET_ACCESS_KEY"]


def create_spark_session():
    """
    Description: Creates a Spark session, and loads related libraries.
    """
    spark = SparkSession \
        .builder \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:2.7.0") \
        .getOrCreate()
    return spark


def process_song_data(spark, input_data, output_data):
    """
    Description: Loads song_data from S3, extracts the songs and artist tables, 
                 and loads the results to another S3 bucket.
    :param spark       : the Spark Session
    :param input_data  : the location of song_data json files
    :param output_data : the output S3 bucket for the dimensional tables in parquet format
    """
    # get filepath to song data file
    song_data_path = os.path.join(input_data, "song_data/A/A/A/*.json")
    
    # read song data file
    df = spark.read.json(song_data_path)

    # extract columns to create songs table
    songs_table = df.select('song_id', 'title', 'artist_id', 'year', 'duration').dropDuplicates()
    
    # write songs table to parquet files partitioned by year and artist
    songs_table.write.partitionBy('year', 'artist_id').parquet(os.path.join(output_data, 'songs.parquet'), 'overwrite')

    # extract columns to create artists table
    artists_table = df.select('artist_id', 'artist_name', 'artist_location', 'artist_latitude', 'artist_longitude').dropDuplicates(['artist_id'])
    
    # write artists table to parquet files
    artists_table.write.parquet(os.path.join(output_data, 'artists.parquet'), 'overwrite')


def process_log_data(spark, input_data, output_data):
    """
    Description: Loads log_data from S3, extracts the songs and artist tables
                 and loads the results to another S3 bucket.
    :param spark       : the Spark Session
    :param input_data  : the location of log_data json files
    :param output_data : the output S3 bucket for the dimensional tables in parquet format
            
    """
    # get filepath to log data file
    log_data_path = os.path.join(input_data,"log_data/*/*/*.json")

    # read log data file
    df = spark.read.json(log_data_path)
    
    # filter by actions for song plays
    songplays_table = df.select('ts', 'userId', 'level','sessionId', 'location', 'userAgent')

    # extract columns for users table    
    artists_table = df.select('userId', 'firstName', 'lastName', 'gender', 'level').dropDuplicates(['userId'])
    
    # write users table to parquet files
    artists_table.write.parquet(os.path.join(output_data, 'users.parquet'), 'overwrite')

    # create timestamp column from original timestamp column
    get_timestamp = udf(lambda x: str(int(int(x)/1000)))
    df = df.withColumn('timestamp', get_timestamp(df.ts))
    
    # create datetime column from original timestamp column
    get_datetime = udf(lambda x: str(datetime.fromtimestamp(int(x) / 1000.0)))
    df = df.withColumn("datetime", get_datetime(df.ts))
    
    # extract columns to create time table
    time_table = df.select(
        col('datetime').alias('start_time'),
        hour('datetime').alias('hour'),
        dayofmonth('datetime').alias('day'),
        weekofyear('datetime').alias('week'),
        month('datetime').alias('month'),
        year('datetime').alias('year') 
    ).dropDuplicates(['start_time'])
    
    # write time table to parquet files partitioned by year and month
    time_table.write.partitionBy('year', 'month').parquet(os.path.join(output_data, 'time.parquet'), 'overwrite')

    # read in song data to use for songplays table
    song_df_path = os.path.join(input_data, "song_data/*/*/*/*.json")
    song_df = spark.read.json(song_df_path)

    # extract columns from joined song and log datasets to create songplays table 
    df = df.join(song_df, song_df.title == df.song)
    
    songplays_table = df.select(
        col('ts').alias('ts'),
        col('userId').alias('user_id'),
        col('level').alias('level'),
        col('song_id').alias('song_id'),
        col('artist_id').alias('artist_id'),
        col('sessionId').alias('session_id'),
        col('location').alias('location'),
        col('userAgent').alias('user_agent'),
        year('datetime').alias('year'),
        month('datetime').alias('month')
    ).withColumn('songplay_id', monotonically_increasing_id())

    # write songplays table to parquet files partitioned by year and month
    songplays_table.write.partitionBy('year', 'month').parquet(os.path.join(output_data, 'songplays.parquet'), 'overwrite')


def main():
    spark = create_spark_session()
    input_data  = "s3a://udacity-dend/"
    output_data = "s3a://datalake-project-2021p"
    
    process_song_data(spark, input_data, output_data)    
    process_log_data(spark, input_data, output_data)


if __name__ == "__main__":
    main()
