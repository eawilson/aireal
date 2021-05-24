import requests
import datetime
import tempfile
import pdb



class Session(object):
    
    def __init__(self, token):
        self.token = token


    def get_raw(self, url, params={}):
        path = f"http://api.basespace.illumina.com/v1pre3/{url}"
        response = requests.get(path,
                                params=params, 
                                headers={"x-access-token": self.token},
                                stream=True)
        if response.status_code != requests.codes.ok:
            try:
                message = response.json()["ResponseStatus"]
            except Exception:
                message = ""
            raise RuntimeError(response.status_code, response.reason, message)
        return response


    def get_single(self, url, params={}):
        return self.get_raw(url, params).json()["Response"]


    def get_multiple(self, url, params={}, limit=10):
        params.update({"Offset": 0, "Limit": limit})
        while True:
            response = self.get_raw(url, params).json()["Response"]
            for item in response["Items"]:
                yield item
            params["Offset"] = response.get("Offset", 0) + response["DisplayedCount"]
            if response["TotalCount"] <= params["Offset"]:
                break


    def get_file(self, file_bsid):
        return self.get_raw(f"files/{file_bsid}/content", params={})


    def iter_file_chunks(self, file_bsid, chunk_size=8*1024):
        for chunk in self.get_file(file_bsid).iter_content(chunk_size=chunk_size):
            yield chunk


    def search(self, scope, **kwargs):
        for row in self.get_multiple("search", params={"scope": scope, **kwargs}):
            if len(row) != 3:
                raise RuntimeError("Unexpected search results.")
            for k, v in row.items():
                if k not in ("Type", "Score"):
                    yield v
                    break
    
    
    def sample_fastqs(self, sample_bsid):
        return [filejson for filejson
                    in self.get_multiple(f"samples/{sample_bsid}/files")
                    if filejson["Name"].endswith(".fastq.gz")]
    

    def download_fileobj(self, file_bsid, fobj):
        bytes = 0
        for chunk in self.iter_file_chunks(file_bsid):
            bytes += len(chunk)
            fobj.write(chunk)
        return bytes


    def file_url(self, file_bsid):
        response = self.get_file(file_bsid)
        response.close()
        return response.url


    def get_rundata(self, run_bsid):
        pass
        
        
        
        
        
class Session2(object):
    
    def __init__(self, token):
        self.token = token
        

    def get_raw(self, url, params={}):
        path = f"http://api.basespace.illumina.com/v2/{url}"
        response = requests.get(path,
                                params=params, 
                                headers={"x-access-token": self.token},
                                stream=True)
        if response.status_code != requests.codes.ok:
            try:
                message = response.json()["ResponseStatus"]
            except Exception:
                message = ""
            raise RuntimeError(response.status_code, response.reason, message)
        return response


    def get_single(self, url, params={}):
        return self.get_raw(url, params).json()


    def get_multiple(self, url, params={}, limit=10):
        params.update({"offset": 0, "limit": limit})
        while True:
            response = self.get_raw(url, params).json()
            for item in response["Items"]:
                yield item
            paging = response["Paging"]
            params["offset"] = paging["Offset"] + paging["DisplayedCount"]
            if paging["TotalCount"] <= params["offset"]:
                break


    def get_file(self, file_bsid):
        return self.get_raw(f"files/{file_bsid}/content", params={})


    def iter_file_chunks(self, file_bsid, chunk_size=8*1024):
        for chunk in self.get_file(file_bsid).iter_content(chunk_size=chunk_size):
            yield chunk


    def search(self, scope, **kwargs):
        for row in self.get_multiple("search", params={"scope": scope, **kwargs}):
            if len(row) != 3:
                raise RuntimeError("Unexpected search results.")
            for k, v in row.items():
                if k not in ("Type", "Score"):
                    yield v
                    break
    
    
    def sample_fastqs(self, sample_bsid):
        return [filejson for filejson
                    in self.get_multiple(f"samples/{sample_bsid}/files")
                    if filejson["Name"].endswith(".fastq.gz")]
    

    def download_fileobj(self, file_bsid, fobj):
        bytes = 0
        for chunk in self.iter_file_chunks(file_bsid):
            bytes += len(chunk)
            fobj.write(chunk)
        return bytes


    def file_url(self, file_bsid):
        response = self.get_file(file_bsid)
        response.close()
        return response.url


    def get_rundata(self, run_bsid):
        pass
        
        
        
        
        
