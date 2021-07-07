import requests
import xlsxwriter
import pandas as pd
import os
import re
import bs4 as bs
from tqdm import tqdm
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from os import path

def cves_from_nvd(search_uri, version):
    try:
        urlopen(search_uri)
    except HTTPError as e:
        print('>> The NVD server couldn\'t fulfill the request.')
        print('>> Error code: ', e.code)
    except URLError as e:
        print('>> We failed to reach a server.')
        print('>> Reason: ', e.reason)
    else:
        response = requests.get(search_uri)
        if response.status_code == 200:
            search_result = response.json()
            if search_result['totalResults'] >= 1:
                cve_dic = {}
                for all_cve in search_result['result']['CVE_Items']:
                    desc = all_cve['cve']['description']['description_data']
                    impact = all_cve['impact']
                    final_desc = desc[0]['value']
                    cvss3_lis = []
                    cvss2_lis = []
                    version_present = "No"
                    component_regex_1 = re.findall(r'(related to)\s(.*?)[\.\,]', final_desc)
                    component_regex_2 = re.findall(r'(subcomponent):(.*?)\)', final_desc)
                    #component = re.findall(r'(affected is) (.*?)\.\s', final_desc)#regex to fetch the affected java versions
                    component = None
                    if component_regex_1:
                        component = component_regex_1
                    else:
                        component = component_regex_2                    
                    final_component = None
                    if len(component) == 0:
                        final_component = "NA"
                    else:
                        final_component = component[0][1]
                    if not len(version) == 0:
                        if version in final_desc:
                            version_present = "Yes"
                    if len(impact) > 1:
                        cvss3_lis.append(impact['baseMetricV3']['cvssV3']['vectorString'])
                        cvss3_lis.append(impact['baseMetricV3']['cvssV3']['baseScore'])
                        cvss3_lis.append(impact['baseMetricV3']['cvssV3']['baseSeverity'])
                        cvss2_lis.append(impact['baseMetricV2']['cvssV2']['vectorString'])
                        cvss2_lis.append(impact['baseMetricV2']['cvssV2']['baseScore'])
                        cvss2_lis.append(impact['baseMetricV2']['severity'])
                    else:
                        cvss2_lis.append(impact['baseMetricV2']['cvssV2']['vectorString'])
                        cvss2_lis.append(impact['baseMetricV2']['cvssV2']['baseScore'])
                        cvss2_lis.append(impact['baseMetricV2']['severity'])
                    bug_short_long_desc = bugzilla_data_extraction(all_cve['cve']['CVE_data_meta']['ID'])
                    # print(bug_short_long_desc)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(final_desc)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(cvss3_lis)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(cvss2_lis)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(final_component)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(version_present)
                    cve_dic.setdefault(all_cve['cve']['CVE_data_meta']['ID'], []).append(bug_short_long_desc)
                # print(cve_dic)
                return cve_dic

def bugzilla_data_extraction(fetch_cve):
	try:
	    URL = "https://bugzilla.redhat.com/show_bug.cgi?id={}".format(fetch_cve)
	    source = urlopen(URL)
	    desc_lis = []
	    if source.getcode() == 200:
	        soup = bs.BeautifulSoup(source, features='lxml')
	        error_check = soup.find('div',  attrs = {'id':'error_msg'})
	        if error_check == None:
	            short_desc = ""
	            long_desc = []
	            for short_paragraph in soup.find('span', attrs = {'id':'short_desc_nonedit_display'}):
	                short_desc = short_paragraph.string
	            desc_lis.append(short_desc)
	            for long_paragraph in  soup.find('pre', attrs = {'class':'bz_comment_text'}):
	            	long_desc.append(long_paragraph.string)
	            desc_initial = " ".join([ld for ld in long_desc])
	            desc_lis.append(desc_initial)
	            flag = False
	            for i in range(20):
	            	id_str = "c{}".format(i)
	            	soup_str = soup.find('div', attrs = {'id':id_str, 'class':'bz_comment'})
	            	if soup_str == None:
	            		continue
	            	else:
	            		desc_2 = None
	            		for long_paragraph in soup_str:
	            			desc_2 = re.findall(r'(Oracle)\s(.*)\.\s', str(long_paragraph))
	            			if not len(desc_2) == 0:
	            				fin_des = ""
	            				if "fixes an unspecified" in desc_2[0][1]:
	            					fin_des = " ".join(k for k in desc_2[0])
	            					desc_lis.append(fin_des)
	            				else:
	            					fin_des = "Fixed in " + desc_2[0][0] +" " + desc_2[0][1]
	            					desc_lis.append(fin_des)
	            				flag = True
	            				break
	            		if flag == True:
	            			break
	        else:
	            desc_lis.append("Bugzilla URL Invalid/Not Found")      
	            desc_lis.append("Bugzilla URL Invalid/Not Found")  
	            desc_lis.append("Bugzilla URL Invalid/Not Found")
	    print(desc_lis)
	    return desc_lis
	except:
		pass


def final_result(final_cve):
    if bool(final_cve):
        with xlsxwriter.Workbook("CVE.xlsx") as workbook:
            format_head = workbook.add_format(
                {'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BB', 'border': 1})
            worksheet = workbook.add_worksheet()
            worksheet.set_column(2, 2, 50)
            worksheet.set_column(14, 14, 60)
            worksheet.set_column(14, 15, 50)
            worksheet.write(0, 0, 'SI No', format_head)
            worksheet.write(0, 1, 'CVE', format_head)
            worksheet.write(0, 2, 'Description', format_head)
            worksheet.write(0, 3, 'Component', format_head)
            worksheet.write(0, 4, 'Vulnerable JDK present in description?', format_head)
            worksheet.write(0, 5, 'CVSS3', format_head)
            worksheet.write(0, 6, 'CVSS3_Severity', format_head)
            worksheet.write(0, 7, 'CVSS3_Score', format_head)
            worksheet.write(0, 8, 'CVSS2', format_head)
            worksheet.write(0, 9, 'CVSS2_Severity', format_head)
            worksheet.write(0, 10, 'CVSS2_Score', format_head)
            worksheet.write(0, 11, 'NVD URL', format_head)
            worksheet.write(0, 12, 'Bugzilla URL', format_head)
            worksheet.write(0, 13, 'Bugzilla Short description', format_head)
            worksheet.write(0, 14, 'Bugzilla long description', format_head)
            worksheet.write(0, 15, 'CVE Fixed Version', format_head)
            format_body = workbook.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
            for i in range(len(final_cve)):
                # print(final_cve[i])
                for k, v in final_cve[i].items():
                    worksheet.write(i+1, 0, i + 1,format_body)
                    worksheet.write(i+1, 1, k,format_body)
                    worksheet.write(i+1, 2, v[0],format_body)
                    worksheet.write(i+1, 3, v[3],format_body)
                    worksheet.write(i+1, 4, v[4],format_body)
                    if len(v[2]) > 0 and len(v[1]) > 0:
                        worksheet.write(i+1, 5, v[1][0],format_body)
                        worksheet.write(i+1, 6, v[1][2],format_body)
                        worksheet.write(i+1, 7, v[1][1],format_body)
                        worksheet.write(i+1, 8, v[2][0],format_body)
                        worksheet.write(i+1, 9, v[2][2],format_body)
                        worksheet.write(i+1, 10, v[2][1],format_body)
                    elif len(v[1]) > 0 and len(v[2]) == 0:
                        worksheet.write(i+1, 5, v[1][0],format_body)
                        worksheet.write(i+1, 6, v[1][2],format_body)
                        worksheet.write(i+1, 7, v[1][1],format_body)
                        worksheet.write(i+1, 8, 'NA',format_body)
                        worksheet.write(i+1, 9, 'NA',format_body)
                        worksheet.write(i+1, 10, 'NA',format_body)
                    else:
                        worksheet.write(i+1, 8, v[2][0],format_body)
                        worksheet.write(i+1, 9, v[2][2],format_body)
                        worksheet.write(i+1, 10, v[2][1],format_body)
                        worksheet.write(i+1, 5, 'NA',format_body)
                        worksheet.write(i+1, 6, 'NA',format_body)
                        worksheet.write(i+1, 7, 'NA',format_body)
                    worksheet.write(i+1, 11, "https://nvd.nist.gov/vuln/detail/{}".format(k),format_body)
                    worksheet.write(i+1, 12, "https://bugzilla.redhat.com/show_bug.cgi?id={}".format(k),format_body)
                    worksheet.write(i+1, 13, v[5][0],format_body)
                    worksheet.write(i+1, 14, v[5][1],format_body)
                    worksheet.write(i+1, 15, v[5][2],format_body)
        print(">> Find the file in the root directory named CVE.xlsx")
    else:
        pass

def extract(path):
    cve_file = open(path, 'rt')
    lines = cve_file.read().split('\n')
    cve_list = []
    for l in lines:
        if not l == "":
            cve_list.append(l)
    cve_file.close()
    return cve_list


if __name__ == '__main__':
    print(">> Multiple CVE description extracter")
    print("-" * 50)
    cve_path = input(">> Input the path of the cve's: ")
    cve_list = extract(cve_path)
    final_lis = []
    version = None
    if input(">>Is JDK a part of this scan?: Y or N: ") == 'Y':
        version = input(">>Enter the JDK version, eg: 8u202: ")
    else:
        version = ""
    # print(bugzilla_data_extraction("CVE-2014-0448"))
    # print(cve_list)
    try:
        for cve in tqdm (cve_list, desc="Grabbing Info on..", ascii=False, ncols=100):
            print("\n>> Extraction for: ", cve)
            sub_dic = cves_from_nvd('https://services.nvd.nist.gov/rest/json/cve/1.0/{}'.format(cve.strip()), version)
            final_lis.append(sub_dic)
        final_result(final_lis)
    except:
        pass

