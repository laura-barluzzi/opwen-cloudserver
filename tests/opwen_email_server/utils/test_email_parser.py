from enum import Enum
from enum import unique
from os.path import abspath
from os.path import dirname
from os.path import join
from unittest import TestCase
import json

import responses

from opwen_email_server.utils import email_parser


TEST_DATA_DIRECTORY = abspath(join(
    dirname(__file__), '..', '..',
    'files', 'opwen_email_server', 'utils', 'test_email_parser'))


@unique
class ImageSize(Enum):
    large = 1
    small = 2


def _given_test_image_base64(size: ImageSize):
    b64_images_file = join(TEST_DATA_DIRECTORY, 'images_base64.json')
    with open(b64_images_file, 'r', encoding='utf-8') as b64_images:
        json_images = json.load(b64_images)
        return json_images[size.name]


class ParseMimeEmailTests(TestCase):
    def test_parses_email_metadata(self):
        mime_email = self._given_mime_email('email-html.mime')

        email = email_parser.parse_mime_email(mime_email)

        self.assertEqual(email.get('from'), 'clemens.wolff@gmail.com')
        self.assertEqual(email.get('subject'), 'Two recipients')
        self.assertEqual(email.get('sent_at'), '2017-02-13 06:25')
        self.assertEqual(email.get('to'), ['clemens@victoria.lokole.ca',
                                           'laura@victoria.lokole.ca'])

    def test_prefers_html_body_over_text(self):
        mime_email = self._given_mime_email('email-html.mime')

        email = email_parser.parse_mime_email(mime_email)

        self.assertEqual(email.get('body'),
                         '<div dir="ltr">Body of the message.</div>\n')

    def test_parses_email_with_cc_and_bcc(self):
        mime_email = self._given_mime_email('email-ccbcc.mime')

        email = email_parser.parse_mime_email(mime_email)

        self.assertEqual(email.get('bcc'), ['laura@lokole.ca'])
        self.assertEqual(email.get('cc'), ['nzola@lokole.ca',
                                           'clemens@lokole.ca'])

    def test_parses_email_with_attachments(self):
        mime_email = self._given_mime_email('email-attachment.mime')

        email = email_parser.parse_mime_email(mime_email)
        attachments = email.get('attachments', [])

        self.assertEqual(len(attachments), 1)
        self.assertStartsWith(attachments[0].get('content'), 'iVBORw0')
        self.assertEqual(attachments[0].get('filename'),
                         'cute-mouse-clipart-mouse4.png')

    @classmethod
    def _given_mime_email(cls, filename, directory=TEST_DATA_DIRECTORY):
        with open(join(directory, filename)) as fobj:
            return fobj.read()

    def assertStartsWith(self, actual, prefix):
        self.assertIsNotNone(actual)
        if not actual.startswith(prefix):
            self.fail('string "{actual}..." does not start with "{prefix}"'
                      .format(actual=actual[:len(prefix)], prefix=prefix))


class GetDomainsTests(TestCase):
    def test_gets_domains(self):
        email = {'to': ['foo@bar.com', 'baz@bar.com', 'foo@com']}

        domains = email_parser.get_domains(email)

        self.assertSetEqual(domains, {'bar.com', 'com'})

    def test_gets_domains_with_cc_and_bcc(self):
        email = {'to': ['foo@bar.com'],
                 'cc': ['baz@bar.com'],
                 'bcc': ['foo@com']}

        domains = email_parser.get_domains(email)

        self.assertSetEqual(domains, {'bar.com', 'com'})


class ResizeImageTests(TestCase):
    error_message = 'If default MAX_WIDTH_IMAGES and/or MAX_HEIGHT_IMAGES were changed ' \
                    'you may need to change the test base64 in "images_base64.json".'

    def test_change_image_size(self):
        input_base64 = _given_test_image_base64(size=ImageSize.large)
        output_base64 = email_parser._change_image_size(input_base64)
        self.assertNotEqual(input_base64, output_base64, self.error_message)

    def test_change_image_size_when_already_small(self):
        input_base64 = _given_test_image_base64(size=ImageSize.small)
        output_base64 = email_parser._change_image_size(input_base64)
        self.assertEqual(input_base64, output_base64, self.error_message)


class ConvertImgUrlToBase64Tests(TestCase):
    @responses.activate
    def test_format_inline_images_with_img_tag(self):
        self.givenTestImage()
        input_email = {'body': '<div><h3>test image</h3><img src="http://test-url.png"/></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertStartsWith(output_email['body'], '<div><h3>test image</h3><img src="data:image/png;')

    @responses.activate
    def test_format_inline_images_with_img_tag_without_src_attribute(self):
        input_email = {'body': '<div><img/></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertEqual(output_email, input_email)

    @responses.activate
    def test_format_inline_images_with_bad_request(self):
        self.givenTestImage(status=404)
        input_email = {'body': '<div><img src="http://test-url.png"/></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertEqual(output_email, input_email)

    @responses.activate
    def test_format_inline_images_with_many_img_tags(self):
        self.givenTestImage()
        input_email = {'body': '<div><img src="http://test-url.png"/><img src="http://test-url.png"/></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertHasCount(output_email['body'], 'src="data:', 2)

    @responses.activate
    def test_format_inline_images_without_img_tags(self):
        input_email = {'body': '<div></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertEqual(output_email, input_email)

    @responses.activate
    def test_format_inline_images_without_content_type(self):
        self.givenTestImage(content_type='')
        input_email = {'body': '<div><img src="http://test-url.png"/></div>'}

        output_email = email_parser.format_inline_images(input_email)

        self.assertStartsWith(output_email['body'], '<div><img src="data:image/png;')

    def assertStartsWith(self, data, prefix):
        self.assertEqual(data[:len(prefix)], prefix)

    def assertHasCount(self, data, snippet, expected_count):
        actual_count = data.count(snippet)
        self.assertEqual(actual_count, expected_count,
                         'Expected {} to occur {} times but got {}'.format(snippet, expected_count, actual_count))

    @classmethod
    def givenTestImage(cls, content_type='image/png', status=200):
        with open(join(TEST_DATA_DIRECTORY, 'test_image.png'), 'rb') as image:
            image_bytes = image.read()

        responses.add(responses.GET, 'http://test-url.png',
                      headers={'Content-Type': content_type},
                      body=image_bytes,
                      status=status)


class FormatAttachedFilesTests(TestCase):
    def test_format_attachments_without_attachment(self):
        input_email = {'attachments': []}

        output_email = email_parser.format_attachments(input_email)

        self.assertEqual(input_email, output_email)

    def test_format_attachments_with_image(self):
        input_filename = 'test_image.png'
        input_content = _given_test_image_base64(size=ImageSize.large)
        attachment = {'filename': input_filename, 'content': input_content}
        input_email = {'attachments': [attachment]}

        output_email = email_parser.format_attachments(input_email)
        output_attachments = output_email.get('attachments', '')

        self.assertEqual(len(output_attachments), 1)

        output_filename = output_attachments[0].get('filename', '')
        output_content = output_attachments[0].get('content', '')

        self.assertNotEqual(input_content, output_content)
        self.assertEqual(input_filename, output_filename)
