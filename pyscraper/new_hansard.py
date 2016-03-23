#! /usr/bin/env python

import re
import json
import os
import sys
from lxml import etree
import xml.sax
xmlvalidate = xml.sax.make_parser()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import codecs
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

parldata = '../../../parldata/'

xml_parser = etree.XMLParser(ns_clean=True)
etree.set_default_parser(xml_parser)


class ParseDayXML(object):
    oral_headings = [
        'hs_3OralAnswers'
    ]
    major_headings = [
        'hs_6bDepartment'
    ]
    minor_headings = [
        'hs_8Question'
    ]
    root = etree.Element('publicwhip')
    ns = {'ns': 'http://www.parliament.uk/commons/hansard/print'}

    debate_type = None
    current_speech = None
    date = '2016-03-15'
    rev = 'a'
    current_col = 0
    current_speech_num = 0
    current_speech_part = 1
    current_time = ''

    def get_pid(self):
        return '{0}{1}.{2}/{3}'.format(
            self.rev,
            self.current_col,
            self.current_speech_num,
            self.current_speech_part
        )

    def get_speech_id(self):
        return 'uk.org.publicwhip/{0}/{1}{2}.{3}.{4}'.format(
            self.debate_type,
            self.date,
            self.rev,
            self.current_col,
            self.current_speech_num
        )

    def check_for_pi(self, tag):
        pi = tag.xpath('.//processing-instruction("notus-xml")')
        if len(pi) == 1:
            self.parse_pi(pi[0])

    def parse_member(self, tag):
        member = None
        if tag.tag == '{http://www.parliament.uk/commons/hansard/print}B':
            member = tag.xpath('.//ns:Member', namespaces=self.ns)[0]
        elif tag.tag == '{http://www.parliament.uk/commons/hansard/print}Member':
            member = tag

        if member is not None:
            return member.get('ContinuationText')

        return None

    def parse_oral_heading(self, heading):
        tag = etree.Element('oral-heading')
        tag.text = heading.text
        self.root.append(tag)

    def parse_major(self, heading):
        tag = etree.Element('major-heading')
        text = u"".join(heading.xpath(".//text()"))
        tag.text = text
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            'http://www.publications.parliament.uk{0}'.format(
                heading.get('url')
            )
        )
        self.root.append(tag)

    def parse_minor(self, heading):
        tag = etree.Element('minor-heading')
        text = u"".join(heading.xpath("./text()"))
        tag.text = text
        self.root.append(tag)

    def parse_question(self, question):
        tag = etree.Element('speech')
        tag.set('id', self.get_speech_id())
        tag.set('time', self.current_time)

        member = question.xpath('.//ns:Member', namespaces=self.ns)[0]
        member = self.parse_member(member)
        if member is not None:
            tag.set('person_id', member)

        text = question.xpath('.//ns:QuestionText/text()', namespaces=self.ns)
        tag.text = u''.join(text)
        self.root.append(tag)

    def parse_para(self, para):
        member = None
        for tag in para:
            if tag.tag == '{http://www.parliament.uk/commons/hansard/print}B' or tag.tag == '{http://www.parliament.uk/commons/hansard/print}Member':
                member = self.parse_member(tag)

        if member is not None:
            if self.current_speech is not None:
                self.current_speech_part = 1
                self.root.append(self.current_speech)
                self.current_speech_num = self.current_speech_num + 1
            self.current_speech = etree.Element('speech')
            self.current_speech.set('person_id', member)
            self.current_speech.set('id', self.get_speech_id())
            self.current_speech.set('colnum', self.current_col)
            self.current_speech.set('time', self.current_time)
            self.current_speech.set(
                'url',
                'http://www.publications.parliament.uk{0}'.format(
                    para.get('url')
                )
            )

        tag = etree.Element('p')
        text = u"".join(para.xpath("./text()"))
        if len(text) == 0:
            return

        tag.set('pid', self.get_pid())
        self.current_speech_part = self.current_speech_part + 1
        tag.text = text

        self.current_speech.append(tag)
        self.check_for_pi(para)

    def parse_brev(self, brev):
        tag = etree.Element('p')
        tag.set('pwmotiontext', 'yes')
        text = u"".join(brev.xpath("./text()"))
        if len(text) == 0:
            return

        tag.set('pid', self.get_pid())
        self.current_speech_part = self.current_speech_part + 1
        tag.text = text
        self.current_speech.append(tag)

    def parse_timeline(self, tag):
        time = u''.join(tag.xpath('.//text()'))
        self.current_time = time

    def parse_pi(self, pi):
        # you would think there is a better way to do this but I can't seem
        # to extract attributes from processing instructions :(
        text = str(pi)
        matches = re.search(r'column=(\d+)\?', text)
        if matches is not None:
            col = matches.group(1)
            self.current_col = col
            self.current_speech_num = 0
            self.current_speech_part = 1

    def parse_day(self, xml_file, out):
        xml = etree.parse(xml_file).getroot()
        commons = xml.xpath('//ns:System[@type="Debate"]', namespaces=self.ns)
        self.current_col = commons[0].get('ColStart')
        for b in commons[0].xpath('.//ns:Fragment/ns:Body', namespaces=self.ns):
            for tag in b:

                # remove annoying namespace for brevities sake
                tag_name = str(tag.tag)
                tag_name = tag_name.replace(
                    '{http://www.parliament.uk/commons/hansard/print}',
                    ''
                )
                if tag_name in self.oral_headings:
                    self.parse_oral_heading(tag)
                elif tag_name in self.major_headings:
                    self.parse_major(tag)
                elif tag_name in self.minor_headings:
                    self.parse_minor(tag)
                elif tag_name == 'Question':
                    self.parse_question(tag)
                elif tag_name == 'hs_Para':
                    self.parse_para(tag)
                elif tag_name == 'hs_brev':
                    self.parse_brev(tag)
                elif tag_name == 'hs_Timeline':
                    self.parse_timeline(tag)
                elif type(tag) is etree._ProcessingInstruction:
                    self.parse_pi(tag)
                else:
                    sys.stderr.write("no idea what to do with {0}\n".format(tag_name))


class ParseDay(object):
    def parse_day(self, fp, text, date):
        out = streamWriter(fp)
        parser = ParseDayXML()
        parser.debate_type = 'debate'
        parser.parse_day(text, out)
        out.write(etree.tostring(parser.root))


if __name__ == '__main__':
    fp = sys.stdout
    xml_file = codecs.open(sys.argv[1], encoding='utf-8')
    date = os.path.basename(sys.argv[1])[2:12]
    ParseDay().parse_day(fp, xml_file, date)
