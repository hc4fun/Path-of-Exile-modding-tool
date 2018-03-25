#!/usr/bin/python3
import binascii
import datetime
import sys
import time
import re
import os
import codecs
import copy
import shutil
import threading
import queue
import poemods_ggpk
import brotli

class manager(object):
    def __init__(self, actionqueue, searchqueue, viewqueue):
        self.modg=poemods_ggpk.listggpkfiles()
        self.actionqueue=actionqueue
        self.searchqueue=searchqueue
        self.viewqueue=viewqueue
        self.sendmessage=queue.Queue()
        self.sendsearch=queue.Queue()
        self.sendview=queue.Queue()
        self.threadskeeprunning=True
        actionthreadthr=threading.Thread(target=self.actionthread, args=(5, ))
        actionthreadthr.start()
        searchthreadthr=threading.Thread(target=self.searchthread, args=(5, ))
        searchthreadthr.start()
        viewthreadthr=threading.Thread(target=self.viewthread, args=(5, ))
        viewthreadthr.start()

    def actionthread(self, i):
        while self.threadskeeprunning is True :
            vala=self.actionqueue.get()
            if vala[0]=="quit" :
                self.threadskeeprunning=False
            elif vala[0]=="scan modg" :
                self.sendmessage.put(["Scanning %s" % (vala[1]), "scan modg", "", True])
                self.modg.rescanggpk(vala[1], vala[2], True)
                if self.modg.ggpkname is None :
                    self.sendmessage.put(["Invalid Content.ggpk : %s." % (vala[1]), "scan modg", "", False])
                else :
                    self.sendmessage.put(["", "scan modg", "", False])
            elif vala[0]=="defragment" :
                self.sendmessage.put(["Defragmenting %s" % (self.modg.ggpkname), "defragment", "", True])
                if os.path.exists(vala[1]) is True :
                    self.modg.defragment(vala[1])
                    self.sendmessage.put(["Defragmented to : %s" % (vala[1]), "defragment", "", False])
                else :
                    self.sendmessage.put(["No path to : %s" % (vala[1]), "defragment", "", False])
            elif vala[0]=="extract" :
                if len(self.modg.fullfilelistdic)>0 :
                    matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                    self.sendmessage.put(["%d files are being extracted..." % (len(matchinglist)), "extract", "", True])
                    with open(self.modg.ggpkname, "rb") as ggpkpointeri :
                        count=0
                        for filename in matchinglist :
                            targetpath=os.path.join("extracted", self.modg.fullfilelistdic[filename]["path"][2:])
                            if os.path.exists(targetpath) is False :
                                os.makedirs(targetpath)
                            targetfilename=os.path.join(targetpath, self.modg.fullfilelistdic[filename]["name"])
                            piece = self.modg.readbinarydata(filename, ggpkpointeri)
                            if filename.endswith(".dds") is True :
                                piece = self.decodedds(piece)
                                if piece is None :
                                    continue
                            with open(targetfilename, "wb") as fout :
                                fout.write(piece)
                            count+=1
                    self.sendmessage.put(["%d files extracted." % (count), "extract", "", False])
                else :
                    self.sendmessage.put(["Please scan backup Content.ggpk first."])
            elif vala[0]=="insert" :
                if os.path.exists("extracted") is False :
                    self.sendmessage.put(["Please select a valid folder."])
                    continue
                if len(self.modg.fullfilelistdic)>0 :
                    matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                    self.sendmessage.put(["%d files are being inserted..." % (len(matchinglist)), "insert", "", True])
                    with open(self.modg.ggpkname, "r+b") as ggpkpointerio :
                        count=0
                        for filename in matchinglist :
                            targetfilename=os.path.join("extracted", filename)
                            if os.path.exists(targetfilename) is True :
                                piece=b''
                                with open(targetfilename, "rb") as fin :
                                    piece=fin.read()
                                if filename.endswith(".dds") is True :
                                    pieceorig = self.modg.readbinarydata(filename, ggpkpointerio)
                                    encodingneeded = self.encodeddsneeded(pieceorig)
                                    if encodingneeded is True :
                                        piece = self.encodedds(piece)
                                writethis = self.modg.generateheader(filename, piece)
                                self.modg.writebinarydata(filename, writethis, ggpkpointerio)
                                count+=1
                    self.modg.saveinfo()
                    self.sendmessage.put(["%d files inserted." % (count), "insert", "", False])
                else :
                    self.sendmessage.put(["Please scan backup Content.ggpk first."])
            elif vala[0]=="modify" :
                if len(self.modg.fullfilelistdic)>0 :
                    matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                    self.sendmessage.put(["%d files are being modified by module : %s" % (len(matchinglist), vala[5]), "modify", vala[6], True])
                    self.modify("mods."+vala[5], matchinglist)
                    self.sendmessage.put(["", "modify", vala[6], False])
                else :
                    self.sendmessage.put(["Please scan your Content.ggpk first."])
            elif vala[0]=="restore" :
                if len(self.modg.fullfilelistdic)==0 :
                    self.sendmessage.put(["Please scan your Content.ggpk first."])
                    continue
                if len(vala[1])+len(vala[2])+len(vala[3])+len(vala[4])==0 :
                    self.sendmessage.put(["Please be more specific in your filters."])
                    continue
                matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                self.sendmessage.put(["%d files are being restored..." % (len(matchinglist)), "restore", "", True])
                with open(self.modg.ggpkname, "r+b") as ggpkpointerio :
                    count=0
                    for filename in matchinglist :
                        if filename in self.modg.keeplist :
                            filedata=self.modg.readbinarydata(filename, ggpkpointerio)
                            if filedata is None :
                                continue
                            writethis = self.modg.generateheader(filename, filedata)
                            self.modg.onlywritebinarydata(filename, writethis, ggpkpointerio)
                            count+=1
                self.modg.saveinfo()
                self.sendmessage.put(["%d files restored." % (count), "restore", "", False])
            elif vala[0]=="replacewith" :
                if len(self.modg.fullfilelistdic)==0 :
                    self.sendmessage.put(["Please scan your Content.ggpk first."])
                    continue
                if len(vala[1])+len(vala[2])+len(vala[3])+len(vala[4])==0 :
                    self.sendmessage.put(["Please be more specific in your filters."])
                    continue
                if len(vala[1])>0 or len(vala[2])>0 :
                    self.sendmessage.put(["Replacing files with automods.txt rules...", "replacewith", "", True])
                    matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                    replacewith=[vala[5]]
                    replacewiththis=self.getfilteredlist(replacewith, [], [], [])
                    if len(replacewiththis)==1 :
                        self.modifyreplace(matchinglist, replacewiththis[0])
                        self.sendmessage.put(["", "replacewith", "", False])
                    else :
                        self.sendmessage.put(["Only one file can replace others.", "replacewith", "", False])
                else :
                     self.sendmessage.put(["No replace restrict/exclude filter found."])

    def encodeddsneeded(self, filedata):
        if filedata is None :
            return False
        if len(filedata)<4 :
            return False
        if filedata[0] == b'*' and filedata[3]>=0x20 :
            return False
        if filedata[:4] == b'DDS ' :
            return False
        else :
            return True

    def encodedds(self, filedata):
        filedatal=len(filedata)
        newdecsize = (filedatal).to_bytes(4, byteorder='little', signed=True)
        filedatamod = newdecsize + brotli.compress(filedata)
        return filedatamod

    def decodedds(self, filedata):
        if filedata is None :
            return None
        if len(filedata)<4 :
            return None
        if filedata[0] == b'*' and filedata[3]>=0x20 :
            return None
        if filedata[:4] == b'DDS ' :
            return filedata
        else :
            size = int.from_bytes(filedata[:4], 'little')
            filedatamod = brotli.decompress(filedata[4:])
            if len(filedatamod)!=size :
                print("brotli decompress error")
                return None
            else :
                return filedatamod

    def modify(self, modulename, matchinglist) :
        mymod=__import__(modulename, fromlist=['bebop'])
        lock = threading.Lock()
        with open(self.modg.ggpkname, "r+b") as ggpkpointerio :
            def worker() :
                while True :
                    filename = q.get()
                    if filename=="" :
                        break
                    with lock:
                        backupfiledata=self.modg.readbinarydata(filename, ggpkpointerio)
                    if backupfiledata is not None :
                        filedatamod, encoding, bom = mymod.execute(filename, backupfiledata, self.modg)
                        if filedatamod is not None :
                            if encoding is None :
                                filedatamodified = filedatamod
                            else :
                                filedatamodified = bom + filedatamod.encode(encoding)
                            writethis = self.modg.generateheader(filename, filedatamodified)
                            with lock:
                                self.modg.writebinarydata(filename, writethis, ggpkpointerio)
                    q.task_done()
            q = queue.Queue()
            for i in range(4) :
                t=threading.Thread(target=worker)
                t.start()
            for filename in matchinglist :
                q.put(filename)
            q.join()
            for i in range(4) :
                q.put("")
        self.modg.saveinfo()

    def modifyreplace(self, matchinglist, replacewiththis) :
        with open(self.modg.ggpkname, "r+b") as ggpkpointerio :
            replacewiththisdata=self.modg.readbinarydata(replacewiththis, ggpkpointerio)
            if replacewiththisdata is None :
                return False
            for filename in matchinglist :
                writethis = self.modg.generateheader(filename, replacewiththisdata)
                self.modg.writebinarydata(filename, writethis, ggpkpointerio)
        self.modg.saveinfo()

    def searchthread(self, i):
        while self.threadskeeprunning is True :
            vala=self.searchqueue.get()
            if vala[0]=="quit" :
                self.threadskeeprunning=False
            elif vala[0]=="search" :
                if len(self.modg.fullfilelistdic)>0 :
                    matchinglist=self.getfilteredlist(vala[1], vala[2], vala[3], vala[4])
                    self.sendsearch.put(matchinglist)
                else :
                    self.sendmessage.put(["Please scan your Content.ggpk first."])

    def viewthread(self, i):
        while self.threadskeeprunning is True :
            while self.viewqueue.qsize()>1 :
                vala=self.viewqueue.get()
                if vala[0]=="quit" :
                    self.threadskeeprunning=False
                    return False
            vala=self.viewqueue.get()
            if vala[0]=="quit" :
                self.threadskeeprunning=False
            elif vala[0]=="view" :
                if vala[1] in self.modg.fullfilelistdic :
                    with open(self.modg.ggpkname, "rb") as ggpkpointerio :
                        result1=self.modg.readbinarydata(vala[1], ggpkpointerio)
                        result2=self.modg.readggpkbinarydata(vala[1], ggpkpointerio)
                        if result1 is None and result2 is None :
                            self.sendmessage.put(["Please scan your Content.ggpk first."])
                        else :
                            same=True
                            if result1!=result2 :
                                same=False
                            result1=self.affiche(result1)
                            result2=self.affiche(result2)
                            self.sendview.put([vala[1], result1, result2, same])
                else :
                    self.sendmessage.put(["Please scan your Content.ggpk first."])

    def affiche(self, ceci):
        if ceci is None :
            return ""
        cecil = len(ceci)
        result=""
        i=0
        while i<cecil :
            if 32 <= ceci[i] <= 126 :
                result+="%c" % (ceci[i])
                if i<cecil-1 :
                    if ceci[i+1] == 0 :
                        i+=1
            elif ceci[i] == 0x9 :
                result+="\\t"
                if i<cecil-1 :
                    if ceci[i+1] == 0 :
                        i+=1
            elif ceci[i] == 0xd :
                result+="\\r"
                if i<cecil-1 :
                    if ceci[i+1] == 0 :
                        i+=1
            elif ceci[i] == 0xa :
                result+="\\n\n"
                if i<cecil-1 :
                    if ceci[i+1] == 0 :
                        i+=1
            elif ceci[i] > 126:
                result+="%02x" % (ceci[i])
            elif ceci[i] < 32:
                result+="%02x" % (ceci[i])
            i+=1
        return result

    def getfilteredlist(self, defrestrict, defexclude, restrict, exclude):
        defrestrictc=[]
        defexcludec=[]
        restrictc=[]
        excludec=[]
        try :
            for loi in defrestrict :
                defrestrictc.append(re.compile(loi, flags=re.IGNORECASE))
            for loi in defexclude :
                defexcludec.append(re.compile(loi, flags=re.IGNORECASE))
            for loi in restrict :
                restrictc.append(re.compile(loi, flags=re.IGNORECASE))
            for loi in exclude :
                excludec.append(re.compile(loi, flags=re.IGNORECASE))
        except Exception as e :
            self.sendmessage.put(["Python.re : %s." % (str(e)), "error"])
            return []
        filteredlist=[]
        for filename in self.modg.fullfilelist :
            if filename[-1]=="/" or len(filename)<=2 :
                continue
            if len(defrestrictc)>0 :
                take=False
                for regex in defrestrictc :
                    if regex.search(filename) is not None :
                        take=True
                        break
                if take is False :
                    continue
            take=True
            for regex in defexcludec :
                if regex.search(filename) is not None :
                    take=False
                    break
            if take is False :
                continue
            if len(restrictc)>0 :
                take=False
                for regex in restrictc :
                    if regex.search(filename) is not None :
                        take=True
                        break
                if take is False :
                    continue
            take=True
            for regex in excludec :
                if regex.search(filename) is not None :
                    take=False
                    break
            if take is False :
                continue
            filteredlist.append(filename)
        return filteredlist


























