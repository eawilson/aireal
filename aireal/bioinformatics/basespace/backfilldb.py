from pipeline import s3_list_keys







for key in s3_list_keys("omdc-data","projects", extension="fastq.gz"):
        print(key)








































