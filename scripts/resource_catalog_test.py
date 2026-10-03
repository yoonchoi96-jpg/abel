from scripts.resource_catalog import build

def main():
    data=build({"items":[
      {"path":"Chinese/LISTENING/HSK6/a.mp3","kind":"listening","language":"zh-CN","level":"HSK6","checksum":"abc"},
      {"path":"Chinese/READING/HSK6/q1.json","kind":"reading","language":"zh-CN","level":"HSK6","checksum":"def"},
      {"path":"Chinese/READING/HSK6/q1.json","kind":"reading","language":"zh-CN","level":"HSK6","checksum":"def"},
    ]})
    assert data["count"]==2
    assert data["items"][0]["resource_id"].startswith("res-")
    print("resource_catalog_test: PASS")

if __name__=="__main__": main()
