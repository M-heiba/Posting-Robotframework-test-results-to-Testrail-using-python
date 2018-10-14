from lxml import etree
import requests
import argparse
import json
import pathlib
import sys, re

#############################


Headers                         = {'Content-Type' : 'application/json'}     

def Play():
    Parse_CLI_arguments()
    Load_config(config_file_path)
    
    Run_results_dict = Create_results_dictionary()
    
    Get_user_ID_from_Testrail()
    
    if UserSpecified_Testrail_testrunID==0:
        Add_testrun_at_Testrail(Run_results_dict)
    else :
        global Testrail_Run_ID 
        Testrail_Run_ID = UserSpecified_Testrail_testrunID

    Post_testResults_toTestrail(Run_results_dict)


def Parse_CLI_arguments():
    
    parser = argparse.ArgumentParser(description="This app posts the automation results to Testrail")
    parser.add_argument("-F", "--XMLPath", help="Path to output.xml of automated robot run", default="XML\\output.xml" )
    parser.add_argument("-C", "--configFile", help="Path to config.json Testrail configuration file", default="config.json" )
    parser.add_argument("-R", "--TRrunID", help="ID of Testrail run to add results to", default=0 )
    parser.add_argument("Website_verion_number", help="Release version that test run against")
    args = parser.parse_args()
    
    # Inform user what is the path specified for the XML file in CLI
    if args.XMLPath == "XML\\output.xml": 
        print("The default path to Output.xml is specified \n    {}\n".format(args.XMLPath))
    else :
        print("Output.xml path is not default, it is specified as: \n    {}\n".format(args.XMLPath))

    Check_file_exists(args.XMLPath)

    # Inform user what is the path specified for the configuration file in CLI
    if args.configFile == "config.json": 
        print("The default path to config.json is specified \n    {}\n".format(args.configFile))
    else :
        print("config.json path is not default, it is specified as: \n    {}\n".format(args.configFile))
        
    Check_file_exists(args.configFile)
    
    global XML_doc_path , config_file_path, Website_verion_number , UserSpecified_Testrail_testrunID
    XML_doc_path=args.XMLPath
    config_file_path=args.configFile   
    Website_verion_number= args.Website_verion_number
    
    UserSpecified_Testrail_testrunID= args.TRrunID
    
    print("Command line arguments parsed successfully :) \n \n")
    
def Check_file_exists(File_Path):
    file_Name = pathlib.PurePath(File_Path).name
    
    try:
        Absolute_path= pathlib.Path(File_Path).resolve(strict=True)
        print("{} file exists in specified path :) \n   {} \n".format(file_Name, Absolute_path))
    except FileNotFoundError:
        Absolute_path_wrong= pathlib.Path(File_Path).resolve()
        print("{} file is not found at the specified URL \n    {}\n".format(file_Name, Absolute_path_wrong))
        sys.exit(1)
        
def Load_config(config_filepath):
    Config_file =open(config_filepath, 'r')
    config = json.load(Config_file)
    global Base_URL
    global Basic_Authentication_username
    global Basic_Authentication_password
    global Testrail_project_id
    Base_URL                        = config["Base_URL"]
    Basic_Authentication_username   = config["Basic_Authentication_username"]
    Basic_Authentication_password   = config["Basic_Authentication_password"]
    Testrail_project_id             = config["Testrail_project_id"]
    print("Configuration loaded from config file :) \n    for user : \n        {} \n    and Testrail URL : \n        {}"
          .format(Basic_Authentication_username, Base_URL))

def Create_results_dictionary():
    #counter to get number of testrail testcases automated
    Countof_testrail_TC_included = 0
    #parsing xml file
    doc = etree.parse(XML_doc_path)
    All_tags = doc.xpath('//statistics/tag/stat')
    Count_of_existing_tags = len(All_tags)
    #Getting date of test run 
    Execution_date_element=doc.xpath('//robot')[0]
    Execution_timestamp = Execution_date_element.get("generated") 
    Execution_date = Execution_timestamp.split()[0] 
    Results_dictionary={'Execution_date': Execution_date}
    
    for Tag_index in range(1, Count_of_existing_tags + 1): 
        #getiing tag text from XMl document
        Tag_xpath = '//statistics/tag/stat['+ str(Tag_index)+ ']'
        Tag_text_unfiltered = doc.findtext(Tag_xpath)
        Tag_element= doc.xpath(Tag_xpath)[0]
        
        Matched_tag = re.search(r"(?i)testrail[_, ]id[=, ,:][c]*\d+", Tag_text_unfiltered )
        
        if Matched_tag:
            Countof_testrail_TC_included +=1
            Matched_testrailID_from_tag= re.search(r"\d+", Matched_tag.group())
            
            Testrail_TC_ID = Matched_testrailID_from_tag.group()
            
            failed_count = int(Tag_element.get("fail"))
            
            if failed_count == 0 : 
                Status = 1    #testcase Passed
            else :               
                Status = 5    #testcase Failed

            Results_dictionary[Testrail_TC_ID] = Status
    print ("XML files has been read successfully ;) it contained {} Testrail TCs".format(Countof_testrail_TC_included))
    return Results_dictionary  

def Get_user_ID_from_Testrail():
    Request_URL = Base_URL + 'index.php?/api/v2/get_user_by_email&email=' + Basic_Authentication_username 
    Response = requests.get(Request_URL , headers = Headers, auth=( Basic_Authentication_username, Basic_Authentication_password))
    if Response.status_code == 200 :
        print("\nSuccessfully got user_id at Testrail \n    for user : {}\n    Testrail_ID : {} \n"
              .format(Basic_Authentication_username, Response.json()['id']))
        global Testrail_User_id
        Testrail_User_id = Response.json()['id']
    else:
        print("\nCouldn't get user id from Testrail \nTestrail response \n{} \nProgram will exit\n".format(Response.json()))
        sys.exit(1)
 

def Add_testrun_at_Testrail(Res_dict):
    Date_of_execution = str(Res_dict['Execution_date'] )
    Res_dict.pop('Execution_date')
    #returning only list of dictionary keys
    testrail_TC_IDs = [*Res_dict]
    Testrail_runName= 'Automation test run on ' + Date_of_execution +' Version ' +Website_verion_number 
    data = {"name":Testrail_runName}
    data['assignedto_id']=Testrail_User_id
    data['include_all']=False
    data['case_ids']=testrail_TC_IDs
    
    Request_body = json.dumps(data)
#     print(Request_body)

    Request_URL = Base_URL + 'index.php?/api/v2/add_run/'+ Testrail_project_id
    response = requests.post( Request_URL , data = Request_body , headers = Headers, 
                            auth=( Basic_Authentication_username, Basic_Authentication_password))
    
    if response.status_code == 200 :
        print("\nSuccessfully created testrun at Testrail \n    for user : {}\n    Testrail_Run_ID : {} \n"
              .format(Basic_Authentication_username, response.json()['id']))
        print('testrail response is \n{}\n'.format(response.json()))
        global Testrail_Run_ID
        Testrail_Run_ID = response.json()['id']
    else:
        print("\nCouldn't create testrun at Testrail \nTestrail response \n{} \nProgram will exit\n"
              .format(response.json()))
        sys.exit(1)

def Post_testResults_toTestrail(Res_dict):
    print(Testrail_Run_ID)
    try :
        objt = Res_dict['Execution_date']
        Res_dict.pop('Execution_date')
    except :
        pass

    res_keys=list(Res_dict)
    List_ofTCs_results_dicts = []
    
    for index in range (0, len(Res_dict)):
        testrail_TC_id=res_keys[index]
        data = {"case_id":res_keys[index]}
        data["status_id"] = Res_dict[testrail_TC_id]
        data["assignedto_id"] = Testrail_User_id 
        List_ofTCs_results_dicts.append(data)
    
    data_complete = {"results":List_ofTCs_results_dicts}
    Request_body = json.dumps(data_complete)
    
    Request_URL = Base_URL + 'index.php?/api/v2/add_results_for_cases/' + str(Testrail_Run_ID)
    response = requests.post( Request_URL , data = Request_body , headers = Headers, 
                            auth=( Basic_Authentication_username, Basic_Authentication_password))
    
    if response.status_code == 200 :
        print("\nSuccessfully posted results to testrun at Testrail \n    for Testrail_Run_ID: {}\n"
              .format(Testrail_Run_ID))
        print("Testrail response is \n{}\n".format(response.json()))
        
    else:
        print("\nCouldn't post results to testrun at Testrail \nTestrail response \n{} \nProgram will exit\n"
              .format(response.json()))
        sys.exit(1)
    
Play()   
    
    
# def Send_results_to_TR(Results):
#     
#     Request_body = '{"results":' + str(Results) + '}'
#     print(Request_body)
#     Request_URL = Base_URL + 'index.php?/api/v2/add_results_for_cases/' + str(Testrail_Run_ID)
#     response = requests.post( Request_URL , data = Request_body , headers = Headers, 
#                               auth=( Basic_Authentication_username, Basic_Authentication_password))
#     
#     print(response.text)
#     print(response.json())
#     print(response.status_code)
#     
#     
# 
#     
# def Create_results_list_of_dict(docu, List_of_tags):    
#     Results_string=''
#     Countof_testrail_TC_included = 0
#     
#     for tag in List_of_tags:
#         indexx = List_of_tags.index(tag) + 1
#         Tag_Name_unfiltered = docu.findtext('//statistics/tag/stat['+str(indexx)+']')
# 
#         Matched_tag = re.search(r"(?i)testrail[_, ]id[=, ,:][c]*\d+", Tag_Name_unfiltered)
#         
#         if Matched_tag:
#             Countof_testrail_TC_included +=1
#             Matched_testrailID_from_tag= re.search(r"\d+", Matched_tag.group())
#             
#             Testrail_TC_ID = Matched_testrailID_from_tag.group()
#             failed_count = int(tag.get("fail"))
#             
#             if failed_count == 0 : 
#                 Status = 1    #testcase Passed
#             else :               
#                 Status = 5    #testcase Failed
#         
#             Test_result_dict= '{"case_id" :' + str(Testrail_TC_ID) + ', "status_id" :' + str(Status) \
#                             + ', "assignedto_id":'+ str(Testrail_User_id) +'} ,'
#             Results_string += Test_result_dict 
#         
#         
# #         try :
# #             Int_TagName=int(Tag_Name_unfiltered)
# # 
# #             failed_count = int(tag.get("fail"))
# #             
# #             if failed_count == 0 : 
# #                 Status = 1    #testcase Passed
# #             else :               
# #                 Status = 5    #testcase Failed
# #             
# # 
# #             Test_result_dict= '{"case_id" :' + str(Int_TagName) + ', "status_id" :' + str(Status) \
# #                             + ', "assignedto_id":'+ str(Testrail_User_id) +'} ,'
# #             Results_string += Test_result_dict 
# #             
# #         except :
# #             pass
#     Results_list = '[' + Results_string[:-1] + ']'   
# #     print(Countof_testrail_TC_included)
# #     print(Results_list)
#     return Results_list
#         # Same function as try block
# #             if isinstance(Tag_Name_unfiltered, int) : pass 
# #             else : pass
# #     
# #     test2 = doc.findtext('//statistics/tag/stat['+str(5)+']')   out 
# #     print(test2)  out
# #     tags = doc.xpath('//statistics/tag//child::text()') 
# #     print(tags)
           
# def Total_executed_TC(docu):
#     All_TCs = docu.findall('//test')
#     Total_num_of_TCs = len(All_TCs)
#     print('Total executed test cases is ' + str(Total_num_of_TCs))
# 
# def Total_existing_tags(docu):
#     All_tags = docu.xpath('//statistics/tag/stat')
#     print('Total number of existing tags is ' + str(len(All_tags)))
#     return All_tags









