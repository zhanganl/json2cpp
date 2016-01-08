#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf8')

import os
import shutil

from pyparsing import *

rapidjson_path = "rapidjson"

######################################## file       template    ####################################

FILE_HEADER = '''#include "base.h"
namespace json2cpp{

'''

FILE_FOOTER = '''

}
'''

BASE_H = '''/*
 * File:   base.h
 * Author: raozf
 *
 * Created on 2015年5月20日, 下午4:26
 */

#ifndef JSON2CPP_BASE_H
#define	JSON2CPP_BASE_H

#include <string>
#include <vector>

/*使用rapidjson做序列化，保证序列化后的json参数有序*/
#include "rapidjson/rapidjson.h"
#include "rapidjson/document.h"
#include "rapidjson/stringbuffer.h"
#include "rapidjson/writer.h"
#include "rapidjson/error/en.h"

#include "macro.h"
namespace json2cpp{

enum{
    ERR_OK = 0x0,
    ERR_REQUEST_CONFIGURE_INVALID = 1000,
    ERR_REQUEST_OPEN_CONFIGURE_FILE_FAILED,
    ERR_REQUEST_CONFIGURE_FILE_ERROR,
    ERR_REQUEST_INIT_IDMAKER_FAILED,
    ERR_REQUEST_FIELD_NOT_SET,
    ERR_REQUEST_HTTP_FAILED,
    ERR_RESPONSE_RETURNED_ERROR_STATE,
    ERR_RESPONSE_PARAM_TO_JSON_FAILED,
    ERR_RESPONSE_FIELD_NOT_SET,
};

//request && response field
template<typename T>
class Field
{
protected:
    T m_tValue;
    std::string m_strName;
    bool m_bNeed;
    bool m_bSet;
public:
    Field(const std::string& strName, bool bNeed = false)
    :m_tValue() //T类型初始化
	,m_strName(strName)
    ,m_bNeed(bNeed)
    ,m_bSet(false)
    {
    }

    virtual ~Field()
    {
    }

    void SetValue(const T& value)
    {
        m_tValue = value;
        m_bSet = true;
    }

    const T& GetValue() const
    {
        return m_tValue;
    }

    bool IsValueSet() const
    {
        return m_bSet;
    }

    bool IsValid() const
    {
        return !((m_bNeed == true) && (m_bSet == false));
    }

    virtual void Clear()
    {
        m_bSet = false;
    }

    const std::string& GetName() const
    {
        return m_strName;
    }

private:
    void SetName(const std::string& strName)
    {
        m_strName = strName;
    }
};

template<typename T>
class VectorField: public Field<T>
{
public:
    VectorField(const std::string& strName, bool bNeed = false)
    :Field<T>::Field(strName, bNeed)
    {
    }

    virtual ~VectorField(){}

    virtual void Clear()
    {
        this->m_tValue.clear();
        this->m_bSet = false;

        //无法编译通过，因为是继承模板类
        //m_bSet = false;
    }
};

class IRequest
{
public:
    IRequest(){};
    virtual ~IRequest(){};

    virtual uint32_t ToJson(std::string& strJson, std::string& strErrMsg) const = 0;
    virtual bool IsValid(std::string& strErrMsg) const = 0;
};

class IResponse
{
public:
    Field<int> m_JSFCode;                                		//JSF协议错误代码             Y
    Field<std::string> m_JSFMessage;                     //JSF协议错误信息

public:
    IResponse()
		:m_JSFCode("code", true)
		,m_JSFMessage("error")
	{
		Init();
	}

    virtual ~IResponse()
	{
	}

    virtual void Init()
	{
		m_JSFCode.Clear();
		m_JSFMessage.Clear();
	}

    virtual uint32_t FromJson(const std::string& strJson, int status)
	{
		uint32_t dwRet = ERR_OK;

		Init();
		if(status == 200)//http:ok
		{
			m_JSFCode.SetValue(0);
			m_JSFMessage.SetValue("");
			return dwRet;
		}

		//http:error
		//可能的http状态：http://jpcloud.jd.com/pages/viewpage.action?pageId=14357054
		//报错时返回的字符串格式通常为：{"code":500,"error":"错误描述"}
		//但也可能是其他格式或非JSON字符串(webserver报错比如404)，所以需要做容错处理
		rapidjson::Document doc;
		if(doc.Parse<0>(strJson.c_str()).HasParseError() || !doc.IsObject())
		{
			dwRet = ERR_RESPONSE_PARAM_TO_JSON_FAILED;
			m_JSFCode.SetValue(dwRet);
			m_JSFMessage.SetValue("string can not be parsed as json object! str:" + strJson);
		}
		else
		{
			if(doc.HasMember("code") && doc["code"].IsInt())
			{
				m_JSFCode.SetValue(doc["code"].GetInt());
			}
			else
			{
				m_JSFCode.SetValue(status);
			}

			if(doc.HasMember("error") && doc["error"].IsString())
			{
				m_JSFMessage.SetValue(doc["error"].GetString());
			}
			else//没有按格式返回错误，就将返回的全部字符串保存起来
			{
				m_JSFMessage.SetValue(strJson);
			}

			dwRet = ERR_RESPONSE_RETURNED_ERROR_STATE;
		}

		//no need
		//IsValid()

		return dwRet;
	}

    virtual bool IsValid(std::string& strErrMsg) const
	{
		CHECK_REQUEST_FIELD(m_JSFCode, strErrMsg);
		CHECK_REQUEST_FIELD(m_JSFMessage, strErrMsg);

		return true;
	}
};

}
#endif	/* JSON2CPP_BASE_H */
'''

MACRO_H = '''/*
 * File:   macro.h
 * Author: raozf
 *
 * Created on 2015年5月20日, 下午4:26
 */

#ifndef JSON2CPP_MACRO_H
#define	JSON2CPP_MACRO_H

namespace json2cpp{

#define CHECK_REQUEST_FIELD(field, strErrMsg)     \\
    if(!field.IsValid()) \\
    {   \\
        strErrMsg.clear(); \\
        strErrMsg.append("field["); \\
        strErrMsg.append(field.GetName()); \\
        strErrMsg.append("] not set."); \\
        return false;   \\
    }

#define TOJSON_REQUEST_FIELD_INT(field, jsonObject, allocator) \\
    if(field.IsValueSet()) \\
    { \\
        jsonObject.AddMember(rapidjson::StringRef(field.GetName().c_str()), field.GetValue(), allocator);\\
    }

//使用const-string，不复制字符串
//http://miloyip.github.io/rapidjson/zh-cn/md_doc_tutorial_8zh-cn.html#CreateModifyValues
#define TOJSON_REQUEST_FIELD_STRING(field, jsonObject, allocator) \\
    if(field.IsValueSet()) \\
    { \\
        jsonObject.AddMember(rapidjson::StringRef(field.GetName().c_str()), rapidjson::StringRef(field.GetValue().c_str()), allocator);\\
    }

#define TOJSON_REQUEST_FIELD_STRING_SETVALUE(field, jsonObject) \\
    if(field.IsValueSet()) \\
    { \\
        jsonObject.SetString(rapidjson::StringRef(field.GetValue().c_str())); \\
    }

#define TOJSON_REQUEST_FIELD_ARRAY(field, jsonObject, allocator) \\
    if(field.IsValueSet()) \\
    { \\
        rapidjson::Value value(rapidjson::kArrayType); \\
        for(std::vector<std::string>::const_iterator it = field.GetValue().begin(); \\
            it != field.GetValue().end(); \\
            it++) \\
        { \\
            value.PushBack(rapidjson::StringRef(it->c_str()), allocator); \\
        } \\
        jsonObject.AddMember(rapidjson::StringRef(field.GetName().c_str()), value, allocator); \\
    }

#define FROMJSON_RESPONSE_FIELD_INT(doc, field) \\
    if(doc.HasMember(field.GetName().c_str()) && doc[field.GetName().c_str()].IsInt()) \\
    { \\
        field.SetValue(doc[field.GetName().c_str()].GetInt()); \\
    }

#define FROMJSON_RESPONSE_FIELD_STRING(doc, field) \\
    if(doc.HasMember(field.GetName().c_str()) && doc[field.GetName().c_str()].IsString()) \\
    { \\
        field.SetValue(doc[field.GetName().c_str()].GetString()); \\
    }

#define JSONVALUE_TOSTRING(json, str) \\
    rapidjson::StringBuffer buffer; \\
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer); \\
    json.Accept(writer); \\
    str= buffer.GetString();

}
#endif	/* JSON2CPP_MACRO_H */
'''

TOJSON_HEADER = '''     virtual uint32_t ToJson(std::string& strJson, std::string& strErrMsg) const
    {
        strJson = "";
        if(IsValid(strErrMsg) == false)
        {
            return ERR_REQUEST_FIELD_NOT_SET;
        }

        rapidjson::Document doc;
        rapidjson::Document::AllocatorType& allocator = doc.GetAllocator();
        rapidjson::Value root(rapidjson::kObjectType);
'''

TOJSON_FOOTER = '''
        JSONVALUE_TOSTRING(root, strJson);
        return ERR_OK;
    }
'''

ISVALID_HEADER = '''    virtual bool IsValid(std::string& strErrMsg) const
    {
'''

ISVALID_FOOTER = '''
        return true;
    }
'''

RESPONSE_INVALID_HEADER = '''       if(!IResponse::IsValid(strErrMsg))
        {
            return false;
        }
'''

INIT_HEADER = '''   virtual void Init()
    {
        IResponse::Init();
'''

INIT_FOOTER = '''   }
'''

FROMJSON_HEADER = '''   virtual uint32_t FromJson(const std::string& strJson, int status)
    {
        uint32_t dwRet = ERR_OK;

        Init();
        dwRet = IResponse::FromJson(strJson, status);
        if(dwRet != ERR_OK)
        {
            return dwRet;
        }

        rapidjson::Document doc;
        if(doc.Parse<0>(strJson.c_str()).HasParseError() || !doc.IsObject())
        {
            dwRet = ERR_RESPONSE_PARAM_TO_JSON_FAILED;
            m_JSFCode.SetValue(dwRet);
            m_JSFMessage.SetValue("parse response failed. " +  std::string(rapidjson::GetParseError_En(doc.GetParseError())));
        }
        else
        {
'''

FROMJSON_FOOTER = '''
            std::string strError;
            if(!IsValid(strError))
            {
                dwRet = ERR_RESPONSE_FIELD_NOT_SET;
                m_JSFCode.SetValue(dwRet);
                m_JSFMessage.SetValue(strError);
            }
        }

        return dwRet;
    }
'''
######################################## classes definition ####################################
class Field:
    def __init__(self):
        self.description = ""
        self.type = ""
        self.name = ""
        self.jdname = ""
        self.optional = 0

    def is_valid(self):
        # return self.type != "" and self.name != "" and self.jdname != ""
        return self.type != "" and self.name != ""

    def get_field_type(self):
        if self.type == "vector<int>":
            return "VectorField<std::vector<int> >"
        elif self.type == "vector<short>":
            return "VectorField<std::vector<short> >"
        elif self.type == "vector<string>":
            return "VectorField<std::vector<std::string> >"
        elif self.type == "string":
            return "Field<std::string>"
        else:
            return "Field<" + self.type + ">"

    def get_tojson_method(self):
        if self.type in ["short", "int"]:
            return "TOJSON_REQUEST_FIELD_INT"
        elif self.type == "string":
            return "TOJSON_REQUEST_FIELD_STRING"
        elif self.type in ["vector<int>", "vector<short>", "vector<string>"]:
            return "TOJSON_REQUEST_FIELD_ARRAY"
        else:
            print "[警告]不支持的变量类型:" + self.type
            return ""

    def get_fromjson_method(self):
        if self.type in ["short", "int"]:
            return "FROMJSON_RESPONSE_FIELD_INT"
        elif self.type == "string":
            return "FROMJSON_RESPONSE_FIELD_STRING"
        elif self.type in ["vector<int>", "vector<short>", "vector<string>"]:
            print u"[警告]不支持的变量类型:" + self.type
            return ""
        else:
            print u"[警告]不支持的变量类型:" + self.type
            return ""

    def dump_declaration(self):
        str = ""
        if self.is_valid():
            str = "\t" + self.get_field_type() + "\t\t\tm_" + self.name + ";"
            if self.description != "":
                str += "\t\t\t//" + self.description.decode("gbk")
        return str

    def dump_initialize_list(self):
        str = ""
        if self.is_valid():
            str += "\t\t,m_" + self.name + "(\"" + self.jdname + "\", " + ("true" if self.optional == 0 else "false") + ")\n"
        return str

    def dump_tojson(self):
        str = ""
        if self.is_valid():
            str = "\t\t" + self.get_tojson_method() + "(m_" + self.name + ", root, allocator);\n"
        return str

    def dump_fromjson(self):
        str = ""
        if self.is_valid():
            str = "\t\t\t" + self.get_fromjson_method() + "(doc, m_" + self.name + ");\n"
        return str

    def dump_isvalid(self):
        str = ""
        if self.is_valid():
            str = "\t\tCHECK_REQUEST_FIELD(m_" + self.name + ", strErrMsg);\n"
        return str

    def dump_init(self):
        str = ""
        if self.is_valid():
            str = "\t\tm_" + self.name + ".Clear();\n"
        return str

class FieldCollector:
    def __init__(self):
        self.fields = []

    def is_valid(self):
        if len(self.fields) == 0:
            return 0
        for field in self.fields:
            if field.is_valid() == 0:
                return 0
        return 1;

    def dump_declaration(self):
        str = "public:\n"
        for field in self.fields:
            str += field.dump_declaration();
            str += "\n"
        return str

    def dump_initialize_list(self):
        str = ""
        for field in self.fields:
            str += field.dump_initialize_list()
        return str

    def dump_isvalid(self):
        str = ""
        for field in self.fields:
            str += field.dump_isvalid()
        return str

class Request(FieldCollector):
    def dump_tojson(self):
        str = ""
        for field in self.fields:
            str += field.dump_tojson()
        return str

class Response(FieldCollector):
    def dump_fromjson(self):
        str = ""
        for field in self.fields:
            str += field.dump_fromjson()
        return str

    def dump_init(self):
        str = ""
        for field in self.fields:
            str += field.dump_init()
        return str

class Interface:
    def __init__(self):
        self.description = ""
        self.name = ""
        self.request = 0
        self.response = 0

    def is_valid(self):
        return  self.name != ""\
            and isinstance(self.request, Request) and self.request.is_valid() \
            and isinstance(self.response, Response) and self.response.is_valid()

    def dump(self):
        request_str = "class " + self.name + "Request: public IRequest\n{\n" \
            + self.request.dump_declaration() \
            + "\npublic:\n" \
            + "\t" + self.name + "Request()\n" \
            + "\t\t:IRequest()\n" \
            + self.request.dump_initialize_list() \
            + "\t{}\n\n" \
            + "\t~" + self.name + "Request()\n\t{}\n\n" \
            + TOJSON_HEADER + "\n"\
            + self.request.dump_tojson()\
            + TOJSON_FOOTER+ "\n"\
            + ISVALID_HEADER \
            + self.request.dump_isvalid() \
            + ISVALID_FOOTER \
            + "};"

        response_str = "class " + self.name + "Response: public IResponse\n{\n" \
            + self.response.dump_declaration() \
            + "\npublic:\n" \
            + "\t" + self.name + "Response()\n" \
            + "\t\t:IResponse()\n" \
            + self.response.dump_initialize_list() \
            + "\t{}\n\n" \
            + "\t~" + self.name + "Response()\n\t{}\n\n" \
            + INIT_HEADER+ "\n"\
            + self.response.dump_init() \
            + INIT_FOOTER +"\n"\
            + FROMJSON_HEADER \
            + self.response.dump_fromjson() \
            + FROMJSON_FOOTER + "\n"\
            + ISVALID_HEADER \
            + RESPONSE_INVALID_HEADER + "\n"\
            + self.response.dump_isvalid() \
            + ISVALID_FOOTER \
            + "};"

        return request_str + "\n\n" + response_str
        #source file



######################################## parse  tokens ####################################
def load_grammar():
    quot = Suppress("\"")
    lbrace = Suppress("{")
    rbrace = Suppress("}")
    lbracket = Suppress("(")
    rbracket = Suppress(")")
    semicolon = Suppress(";")
    at = Suppress("@")
    equal = Suppress("=")
    word = Word(alphanums + "_/")
    interface_key = "Interface"
    interface_name = word
    request_key = "Request"
    response_key = "Response"
    description_key = "description"
    optional_key = "optional"
    field_name = word

    field_type = oneOf("short int string vector<short> vector<int> vector<string>")
    description = Group(lbracket + at + description_key + equal + quotedString + rbracket)
    jdname = Group(at + word + equal + quotedString)
    field = Group(Optional(description) +  jdname + field_type + field_name + Optional(optional_key) + semicolon)
    request = Group(request_key + lbrace + OneOrMore(field) + rbrace + semicolon)
    response = Group(response_key + lbrace + OneOrMore(field) + rbrace + semicolon)
    interface = Group(Optional(description) \
        + interface_key + interface_name + lbrace \
        + request \
        + response\
        + rbrace + semicolon)

    return OneOrMore(interface).ignore(cppStyleComment)

def parse_interface(interface_token):
    if type(interface_token) != list:
        print u"[错误]不支持的interface_token类型：" + type(interface_token)
        print interface_token

    interface = Interface()
    interface_token_len = len(interface_token)

    #interface description
    description_dis = 0
    if interface_token_len == 5:    #有注释
        interface.description = parse_description(interface_token[0])
        description_dis = 1
    elif interface_token_len != 4:
        print u"[错误]expected interface_token_len is [4-5], actually is :" + str(interface_token_len)
        print interface_token
        return

    #interface keyword
    #interface_token[description_dis]

    #interface name
    interface_name = interface_token[description_dis + 1]
    if type(interface_name) != str:
        print u"[错误]错误的接口名类型." + type(interface_name)
        print interface_name
        return
    interface.name = interface_name

    #interface request
    interface_request = interface_token[description_dis + 2]
    interface.request = parse_request(interface_request)

    #interface response
    interface_response = interface_token[description_dis + 3]
    if type(interface_response) != list:
        print u"[错误]错误的response类型." + type(interface_response)
        print interface_response
        return
    interface.response = parse_response(interface_response)

    return interface

def parse_description(description_tokens):
    if type(description_tokens) == list and len(description_tokens) == 2:
        if type(description_tokens[1] == str) and description_tokens[1] != "":
            return description_tokens[1]
    return ""

def parse_request(request_tokens, object_type = "request"):
    if type(request_tokens) != list:
        print u"[错误]错误的request/response类型." + str(type(request_tokens))
        print request_tokens
        return

    request_token_len = len(request_tokens)
    if request_token_len  <2:
        print u"[错误]request/response缺少有效字段.期望字段数[>=2],实际字段数:" + str(request_token_len)
        print request_tokens
        return

    object = Request() if (object_type == "request") else Response()
    for i in range(request_token_len):
        if i == 0 :
            #request/response keyword
            pass
        else:
            field = parse_field(request_tokens[i])
            if isinstance(field, Field) and field.is_valid():
                object.fields.append(field)
    return object

def parse_response(response_tokens):
    return parse_request(response_tokens, "response")

def parse_field(field_tokens):
    if type(field_tokens) != list:
        print u"[错误]错误的field类型." + str(type(field_tokens))
        print field_tokens
        return

    field_token_len = len(field_tokens)
    if field_token_len > 5 or field_token_len < 3:
        print u"[错误]expected field_token_len is [3-5], actually is :" + str(field_token_len)
        print field_tokens
        return

    field = Field()

    #field description
    description_dis = 0
    if type(field_tokens[0]) == list: #注释
        field_description_token = parse_description(field_tokens[0])
        if field_description_token == "":
            print u"[警告]无效的注释，已忽略."
            print field_tokens[0]
        field.description = field_description_token
        description_dis = 1

    #field jdname
    field_jdname_token = field_tokens[description_dis]
    if type(field_jdname_token) == list: #注释
        jdname = parse_description(field_jdname_token)
        if jdname == "":
            print u"[警告]无效的注释，已忽略."
            print field_jdname_token
            return
        field.jdname = jdname.strip("\"")
    else:
        print u"[错误]无效的field jdname类型." + str(type(field_jdname_token))
        print field_jdname_token
        return

    #field type
    field_type_token = field_tokens[description_dis + 1]
    if type(field_type_token) != str:
        print u"[错误]错误的field type类型." + str(type(field_type_token))
        print field_type_token
        return
    field.type = field_type_token

    #field name
    field_name_token = field_tokens[description_dis + 2]
    if type(field_name_token) != str:
        print u"[错误]错误的field_name类型." + str(type(field_name_token))
        print field_name_token
        return
    field.name = field_name_token

    #field optional
    if field_token_len == (description_dis + 3) + 1:
        field_optional_token = field_tokens[description_dis + 3]
        if type(field_optional_token) == str and field_optional_token == "optional":
            field.optional = 1
        else:
            print u"[警告]无效的字段修饰符:" + field_optional_token + ". 已忽略"
    return field



######################################## generate c++ files ####################################
def generate_base(base_directory):
    macro_h = open(base_directory + os.sep + "macro.h", "w")
    macro_h.write(MACRO_H)
    macro_h.close()

    base_h = open(base_directory + os.sep + "base.h", "w")
    base_h.write(BASE_H)
    base_h.close()

    #rapidjson library
    if os.path.exists(rapidjson_path) == False:
        print u"[错误]rapidjson库路径不存在." + os.path.abspath(rapidjson_path)
        exit(-1)
    if os.path.isdir(rapidjson_path) == False:
        print u"[错误]rapidjson库路径不是目录." + os.path.abspath(rapidjson_path)
        exit(-1)

    try:
        rapidjson_directory = base_directory + os.sep + "rapidjson"
        if os.path.exists(rapidjson_directory) == True:
            shutil.rmtree(rapidjson_directory)
        shutil.copytree(os.path.abspath(rapidjson_path), rapidjson_directory)
    except Exception, e:
        print e

def generate_interface(base_directory, interface):
    header =  FILE_HEADER + interface.dump() + FILE_FOOTER

    header_h = open(base_directory + os.sep + interface.name + ".h", "w")
    header_h.write(header)
    header_h.close()


def generate_files(tokens, base_directory):
    if type(tokens) != list or len(tokens) < 1:
        print u"[错误]无效的tokens. type:" + type(tokens) + ", len:" + len(tokens)
        print tokens
        return

    #base files
    generate_base(base_directory)

    for interface_token in tokens:
        interface = parse_interface(interface_token)
        generate_interface(base_directory, interface)



########################################      main           ####################################
def usage():
    print "json2cpp {grammar_file} {generated_directory}"

def parse_param(argv):
    grammar_file = argv[1]
    base_directory = argv[2]

    if os.path.exists(grammar_file) == False:
        print u"[错误]文件不存在:" + os.path.abspath(grammar_file)
        exit(-1)

        if os.path.isfile(grammar_file) == False:
            print u"[错误]" + os.path.abspath(grammar_file) + u"不是有效的文件."
            exit(-1)

    base_directory = base_directory + os.sep + "jsf"
    if os.path.exists(base_directory) == False:
        try:
            os.makedirs(base_directory)
        except OSError, why:
            print u"[错误]创建目标文件夹." + os.path.abspath(base_directory) + u"失败."
            exit(-1)

    return os.path.abspath(grammar_file), os.path.abspath(base_directory)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        usage()
        exit(-1)

    file_path = parse_param(sys.argv)
    grammar = load_grammar()
    tokens = grammar.parseFile(file_path[0]).asList()
    generate_files(tokens, file_path[1])