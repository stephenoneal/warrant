import os
import json
import unittest
import datetime

from mock import patch
from envs import env
from placebo.utils import placebo_session
from botocore.exceptions import ClientError

from warrant import Cognito,UserObj,attribute_dict
from warrant.aws_srp import AWSSRP, long_to_hex, hex_to_long


AWSSRP_TEST_FILE = 'awssrp_test_variables.json'


class UserObjTestCase(unittest.TestCase):

    def setUp(self):
        self.user_metadata = {
            'user_status': 'CONFIRMED',
            'username': 'bjones',
        }
        self.user_info = [
            {'Name': 'name', 'Value': 'Brian Jones'},
            {'Name': 'given_name', 'Value': 'Brian'},
            {'Name': 'birthdate', 'Value': '12/7/1980'}
        ]

    def test_init(self):
        u = UserObj('bjones', self.user_info, self.user_metadata)
        self.assertEqual(u.pk,self.user_metadata.get('username'))
        self.assertEqual(u.name,self.user_info[0].get('Value'))
        self.assertEqual(u.user_status,self.user_metadata.get('user_status'))


class AttributeDictTestCase(unittest.TestCase):

    def test_func(self):
        ad = attribute_dict({'username':'bjones','email':'bjones@example.com'})
        self.assertEqual([
            {'Name':'username','Value':'bjones'},
            {'Name':'email','Value':'bjones@example.com'}
        ],ad)


class CognitoTestCase(unittest.TestCase):

    def setUp(self):
        self.cognito_user_pool_id = env('COGNITO_USER_POOL_ID')
        self.app_id = env('COGNITO_APP_ID')
        self.username = env('COGNITO_TEST_USERNAME')
        self.password = env('COGNITO_TEST_PASSWORD')
        self.user = Cognito(self.cognito_user_pool_id,self.app_id,
                         self.username)

    @placebo_session
    def test_authenticate(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        self.assertNotEqual(self.user.access_token,None)
        self.assertNotEqual(self.user.id_token, None)
        self.assertNotEqual(self.user.refresh_token, None)

    @placebo_session
    def test_logout(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        self.user.logout()
        self.assertEqual(self.user.id_token,None)
        self.assertEqual(self.user.refresh_token,None)
        self.assertEqual(self.user.access_token,None)

    @placebo_session
    def test_register(self,session):
        self.user.switch_session(session)
        res = self.user.register('sampleuser','sample4#Password',
                given_name='Brian',family_name='Jones',
                name='Brian Jones',
                email='bjones39@capless.io',
                phone_number='+19194894555',gender='Male',
                preferred_username='billyocean')
        #TODO: Write assumptions


    @placebo_session
    def test_renew_tokens(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        acc_token = self.user.access_token
        self.user.renew_access_token()
        acc_token_b = self.user.access_token
        self.assertNotEqual(acc_token,acc_token_b)

    @placebo_session
    def test_update_profile(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        self.user.update_profile({'given_name':'Jenkins'})
        u = self.user.admin_get_user()
        self.assertEquals(u.given_name,'Jenkins')

    @placebo_session
    def test_admin_get_user(self,session):
        self.user.switch_session(session)
        u = self.user.admin_get_user()
        self.assertEqual(u.pk,self.username)

    @placebo_session
    def test_send_verification(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        self.user.send_verification()
        with self.assertRaises(ClientError) as vm:
            self.user.send_verification(attribute='randomattribute')

    @placebo_session
    def test_check_token(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        og_acc_token = self.user.access_token
        self.user.check_token()
        self.assertNotEquals(og_acc_token,self.user.access_token)


    @patch('warrant.Cognito', autospec=True)
    def test_validate_verification(self,cognito_user):
        u = cognito_user(self.cognito_user_pool_id,self.app_id,
                     username=self.username)
        u.validate_verification('4321')

    @patch('warrant.Cognito', autospec=True)
    def test_confirm_forgot_password(self,cognito_user):
        u = cognito_user(self.cognito_user_pool_id, self.app_id,
                         username=self.username)
        u.confirm_forgot_password('4553','samplepassword')
        with self.assertRaises(TypeError) as vm:
            u.confirm_forgot_password(self.password)

    @placebo_session
    def test_change_password(self,session):
        self.user.switch_session(session)
        self.user.authenticate(self.password)
        self.user.change_password(self.password,'crazypassword$45DOG')

        with self.assertRaises(TypeError) as vm:
            self.user.change_password(self.password)

    def test_set_attributes(self):
        u = Cognito(self.cognito_user_pool_id,self.app_id)
        u._set_attributes({
                'ResponseMetadata':{
                    'HTTPStatusCode':200
                }
        },
            {
                'somerandom':'attribute'
            }
        )
        self.assertEquals(u.somerandom,'attribute')

    @placebo_session
    def test_authenticate_user(self, session):
        self.user.switch_session(session)
        self.user.authenticate_user(self.password)
        self.assertNotEqual(self.user.access_token,None)
        self.assertNotEqual(self.user.id_token, None)
        self.assertNotEqual(self.user.refresh_token, None)


class AWSSRPTestCase(unittest.TestCase):

    def setUp(self):
        self.cognito_user_pool_id = env('COGNITO_USER_POOL_ID')
        self.app_id = env('COGNITO_APP_ID')
        self.username = env('COGNITO_TEST_USERNAME')
        self.password = env('COGNITO_TEST_PASSWORD')
        self.const_username = 'bjones'
        self.const_password = 'ooV8chahghai6uo2uvag'
        self.const_timestamp = 'Thu Mar 23 19:17:44 UTC 2017'
        self.aws = AWSSRP(username=self.username, password=self.password,
                          pool_id=self.cognito_user_pool_id,
                          client_id=self.app_id)
        cur_path = os.path.dirname(__file__)
        file_path = os.path.abspath(os.path.join(cur_path, AWSSRP_TEST_FILE))
        self.test_data = json.load(open(file_path, 'r'))

    def tearDown(self):
        del self.aws

    def test_k_value(self):
        self.assertEqual(
            long_to_hex(self.aws.k),
            '538282c4354742d7cbbde2359fcf67f9f5b3a6b08791e5011b43b8a5b66d9ee6')

    def test_calculate_a(self):
        self.aws.small_a_value = hex_to_long(self.test_data['small_a_value'])
        self.assertEqual(long_to_hex(self.aws.calculate_a()),
                         self.test_data['large_a_value'])

    def test_process_challenge(self):
        self.aws.small_a_value = hex_to_long(self.test_data['small_a_value'])
        self.aws.large_a_value = hex_to_long(self.test_data['large_a_value'])
        challenge = {'SALT': self.test_data['salt'],
                     'SRP_B': self.test_data['server_b_value'],
                     'USER_ID_FOR_SRP': self.const_username,
                     'SECRET_BLOCK': self.test_data['secret_block']}
        response = self.aws.process_challenge(
            challenge, test_timestamp=self.const_timestamp)
        self.assertEqual(response['USERNAME'], self.const_username)
        self.assertEqual(response['PASSWORD_CLAIM_SECRET_BLOCK'],
                         self.test_data['secret_block'])
        self.assertEqual(response['PASSWORD_CLAIM_SIGNATURE'],
                         'RKh3PCqUQNXk0E0SBzCYvIBrfhJOQAYSHccPHL9M2f8=')
        self.assertEqual(response['TIMESTAMP'], self.const_timestamp)

    def test_get_password_authentication_key(self):
        self.aws.small_a_value = hex_to_long(self.test_data['small_a_value'])
        self.aws.large_a_value = hex_to_long(self.test_data['large_a_value'])
        hkdf = self.aws.get_password_authentication_key(
            self.const_username, self.const_password, hex_to_long(self.
            test_data['server_b_value']), self.test_data['server_b_value'])
        self.assertEqual(hkdf, 'm??\x06\x9f8\xbe)\x88K\xf4\xa4y\x06?e')


if __name__ == '__main__':
    unittest.main()