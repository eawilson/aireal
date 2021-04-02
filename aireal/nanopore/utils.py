import json
import os
import pdb
from collections import defaultdict
from ast import literal_eval

from flask import request

from limscore import iso8601_to_utc


def parse_run_files():
    try:
        # Already a dict but need to make we have not been sent something else.
        sizes = dict(json.loads(request.form["sizes"]))
    except Exception:
        raise RuntimeError("Failed to retrieve worklist.")
    
    run_info = {"Manufacturer": "Oxford Nanopore Technologies"}
    root_dir = set()
    files = {}
    for upload in request.files.getlist("files"):
        try:
            size = sizes[upload.filename]
        except (KeyError, TypeError):
            raise RuntimeError("Failed to retrieve worklist.")
        path = upload.filename.replace("\\", "/").split("/")
        name, ext = os.path.splitext(path[-1])
        
        if ext in (".fastq", ".fast5"):
            if len(path) < 4:
                raise RuntimeError("Unexpexted structure of upload directory.")
            root_dir.add(path[-4])
            if path[-3].endswith("_pass"):
                # barcode / fastq/5_pass / filename
                files[path[-1]] = size
                
        else:
            if len(path) < 2:
                raise RuntimeError("Unexpexted structure of upload directory.")
            root_dir.add(path[-2])
            
            files[path[-1]] = size
            
            if path[-1].startswith("final_summary_") and path[-1].endswith(".txt"):
                for row in upload:
                    row = row.decode(errors="ignore")
                    keyval = row.strip().split("=")
                    if len(keyval) == 2:
                        key, val = keyval
                        if key == "instrument":
                            run_info["Machine"] = val
                        elif key == "flow_cell_id":
                            run_info["Flow Cell Id"] = val
                        elif key == "sample_id":
                            run_info["Experiment Name"] = val
                        elif key == "protocol":
                            val = val.split(":")
                            if len(val) > 1:
                                run_info["Kit"] = val[-2]
                        elif key == "started":
                            run_info["Started"] = iso8601_to_utc(val).isoformat()
                        elif key == "processing_stopped":
                            run_info["Stopped"] = iso8601_to_utc(val).isoformat()
                        elif key == "acquisition_run_id":
                            run_info["Run ID"] = val
                            
                upload.close()
            
            elif path[-1].startswith("report_") and path[-1].endswith(".md"):
                rows = []
                started = False
                for row in upload:
                    row = row.decode(errors="ignore").strip()
                    if not started and row == "{":
                        started = True
                    elif started:
                        if row == "}":
                            break
                        row = row.strip('",').split('": "')
                        if len(row) == 2:
                            key, val = row
                            if key == "device_type":
                                run_info["Platform"] = val
                            elif key == "flow_cell_product_code":
                                run_info["Flow Cell Type"] = val
                            elif key == "guppy_version":
                                run_info["Basecaller"] = f"Guppy v{val}"
                            elif key == "version":
                                run_info["Software"] = f"MinKNOW v{val}"

    if len(root_dir) != 1:
        raise RuntimeError("Only a single upload directory can be selected.")
    
    if "Experiment Name" not in run_info:
        raise RuntimeError("Unable to identify experiment name.")
    
    if "Run ID" not in run_info:
        raise RuntimeError("Unable to identify Run ID.")
    
    barcode = None
    extension = None
    for filename in sorted(files):
        ext = fn[-6:]
        if ext in (".fastq", ".fast5"):
            splitname = fn[:-6].split("_")
            if len(splitname) != 5:
                raise RuntimeError(f"Unrecognised file name format: {fn}.")
            if splitname[1] == "pass":############################################### need to sort out fails
                if splitname[2] != barcode or ext != extension:
                    barcode = splitname[2]
                    extension = ext
                    index = 0
                if splitname[4] != str(index):
                    raise RuntimeError(f"Missing file prior to: {fn}.")
                
    run_info["Status"] = "Complete"
    return (run_info, files)
    


#def parse_run_files():
    #try:
        ## Already a dict but need to make we have not been sent something else.
        #sizes = dict(json.loads(request.form["sizes"]))
    #except Exception:
        #raise RuntimeError("Failed to retrieve worklist.")
    
    #run_info = {"Manufacturer": "Oxford Nanopore Technologies"}
    #root_dir = set()
    #data_files = defaultdict(lambda:defaultdict(list))
    #run_files = []
    #for upload in request.files.getlist("files"):
        #try:
            #size = sizes[upload.filename]
        #except (KeyError, TypeError):
            #raise RuntimeError("Failed to retrieve worklist.")
        #path = upload.filename.replace("\\", "/").split("/")
        #name, ext = os.path.splitext(path[-1])
        
        #if ext in (".fastq", ".fast5"):
            #if len(path) < 4:
                #raise RuntimeError("Unexpexted structure of upload directory.")
            #root_dir.add(path[-4])
            #if path[-3].endswith("_pass"):
                ## barcode / fastq/5_pass / filename
                #data_files[path[-2]][path[-3]] += [(path[-1], size)]
                
        #else:
            #if len(path) < 2:
                #raise RuntimeError("Unexpexted structure of upload directory.")
            #root_dir.add(path[-2])
            
            #run_files += [size]
            
            #if path[-1].startswith("final_summary_") and path[-1].endswith(".txt"):
                #for row in upload:
                    #row = row.decode(errors="ignore")
                    #keyval = row.strip().split("=")
                    #if len(keyval) == 2:
                        #key, val = keyval
                        #if key == "instrument":
                            #run_info["Machine"] = val
                        #elif key == "flow_cell_id":
                            #run_info["Flow Cell Id"] = val
                        #elif key == "sample_id":
                            #run_info["Experiment Name"] = val
                        #elif key == "protocol":
                            #val = val.split(":")
                            #if len(val) > 1:
                                #run_info["Kit"] = val[-2]
                        #elif key == "started":
                            #run_info["Started"] = iso8601_to_utc(val).isoformat()
                        #elif key == "processing_stopped":
                            #run_info["Stopped"] = iso8601_to_utc(val).isoformat()
                        #elif key == "acquisition_run_id":
                            #run_info["Run ID"] = val
                            
                #upload.close()
            
            #elif path[-1].startswith("report_") and path[-1].endswith(".md"):
                #rows = []
                #started = False
                #for row in upload:
                    #row = row.decode(errors="ignore").strip()
                    #if not started and row == "{":
                        #started = True
                    #elif started:
                        #if row == "}":
                            #break
                        #row = row.strip('",').split('": "')
                        #if len(row) == 2:
                            #key, val = row
                            #if key == "device_type":
                                #run_info["Platform"] = val
                            #elif key == "flow_cell_product_code":
                                #run_info["Flow Cell Type"] = val
                            #elif key == "guppy_version":
                                #run_info["Basecaller"] = f"Guppy v{val}"
                            #elif key == "version":
                                #run_info["Software"] = f"MinKNOW v{val}"

    #if len(root_dir) != 1:
        #raise RuntimeError("Only a single upload directory can be selected.")
    
    #if "Experiment Name" not in run_info:
        #raise RuntimeError("Unable to identify experiment name.")
    
    #if "Run ID" not in run_info:
        #raise RuntimeError("Unable to identify Run ID.")
    
    ##for barcode in data_files.values():
        ##if len(barcode.get("fastq_pass", ())) != len(barcode.get("fast5_pass", ())):
            ##raise RuntimeError("Different number of fastq and fast5 files found in upload directory.")
    
    #run_info["Status"] = "Complete"
    #return (run_info, data_files, run_files)
    
