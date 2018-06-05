
import getpass
import json
import base64
import time
import sys
import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
import pyperclip
from passwordgenerator import pwgenerator

from ..modules.misc import confirm, lock_prefix


class Vault:

    config = None  # Will hold user configuration
    vaultPath = None  # Vault file location
    vault = None  # Vault content once decrypted
    timer = None  # Set a timer to autolock the vault
    clipboardSignature = None  # Hash of clipboard item
    masterKey = None  # Master key

    def __init__(self, config, vaultPath):
        self.config = config
        self.vaultPath = vaultPath

    def addItemInput(self):
        """
            Add a new secret based on user input
        """

        # Set auto lock timer (to prevent immediate re-locking)
        self.setAutoLockTimer()

        if self.vault.get('categories'):
            # Show categories
            print()
            print("* Available categories:")
            self.categoriesList()
            print()

            # Category ID
            while True:
                try:
                    categoryId = self.input(
                        '* Choose a category number (or leave empty for none): ')
                    break
                except KeyboardInterrupt as e:
                    # Back to menu if user cancels
                    print()
                    return
                except Exception as e:  # Other Exception
                    print()
                    pass

            if categoryId != '':
                if not self.categoryCheckId(categoryId):
                    print('Invalid category. Please try again.')
                    self.addItemInput()
        else:
            print()
            categoryId = ''
            print("* Category: you did not create a category yet. Create one from the main menu to use this feature!")

        # Basic settings
        try:
            name = self.input('* Name / URL: ')
            login = self.input('* Login: ')
            print('* Password suggestion: %s' % (pwgenerator.generate()))
            password = getpass.getpass('* Password: ')

            # Notes
            print('* Notes: (press [ENTER] twice to complete)')
            notes = []
            while True:
                input_str = self.input("> ")
                if input_str == "":
                    break
                else:
                    notes.append(input_str)
        except KeyboardInterrupt as e:
            return

        # Save item
        self.addItem(categoryId, name, login, password, "\n".join(notes))

        # Confirmation
        print()
        print('The new item has been saved to your vault.')
        print()

    def addItem(self, categoryId, name, login, password, notes):
        """
            Add a new secret to the vault
        """

        # Create `secret` item if necessary
        if not self.vault.get('secrets'):
            self.vault['secrets'] = []

        # Add item to vault
        self.vault['secrets'].append({
            'category': categoryId,
            'name': name,
            'login': login,
            'password': password,
            'notes': notes
        })

        self.saveVault()

    def get(self, id):
        """
            Quickly retrieve an item from the vault with its ID
        """

        # Set auto lock timer (to prevent immediate re-locking)
        self.setAutoLockTimer()

        try:
            # Get item
            item = self.vault['secrets'][int(id)]

            # Show item in a table
            results = [[
                self.categoryName(item['category']),
                item['name'],
                item['login']
            ]]
            from tabulate import tabulate
            print()
            print(tabulate(results, headers=[
                  'Category', 'Name / URL', 'Login']))

            # Show eventual notes
            if item['notes'] != '':
                print()
                print('Notes:')
                print(item['notes'])

            # Show item menu
            return self.itemMenu(int(id), item)
        except Exception as e:
            print(e)
            print('Item does not exist.')

    def itemMenu(self, itemKey, item):
        """
            Item menu
        """

        while (True):
            # Check then set auto lock timer
            self.checkThenSetAutoLockTimer()

            print()
            while True:
                try:
                    command = self.input(
                        'Choose a command [copy (l)ogin or (p)assword to clipboard / sh(o)w password / (e)dit / (d)elete / (s)earch / (b)ack to Vault]: ')
                    break
                except KeyboardInterrupt as e:
                    # Back to menu if user cancels
                    print()
                    return
                except Exception as e:  # Other Exception
                    print()
                    pass

            # Ensure the input is lowercased
            command = command.lower()

            # Action based on command
            if command == 'l':  # Copy login to the clipboard
                self.itemCopyToClipboard(item['login'], 'login')
            elif command == 'p':  # Copy a secret to the clipboard
                self.itemCopyToClipboard(item['password'])
            elif command == 'o':  # Show a secret
                self.itemShowSecret(item['password'])
            elif command == 'e':  # Edit an item
                self.itemEdit(itemKey, item)
                return
            elif command == 'd':  # Delete an item
                self.itemDelete(itemKey)
                return
            elif command in ['s', 'b', 'q']:  # Common commands
                return command

    def itemCopyToClipboard(self, item, name='password'):
        """
            Copy an item to the clipboard
        """

        # Copy to clipboard
        self.clipboard(item)
        print('* The %s has been copied to the clipboard.' % (name))
        self.waitAndEraseClipboard()

    def itemShowSecret(self, password):
        """
            Show a secret for X seconds and erase it from the screen
        """

        try:
            print("The password will be hidden after %s seconds." %
                  (self.config['hideSecretTTL']))
            print('The password is: %s' % (password), end="\r")

            time.sleep(int(self.config['hideSecretTTL']))
        except KeyboardInterrupt as e:
            # Will catch `^-c` and immediately hide the password
            pass

        print('The password is: ' + '*' * len(password))

    def itemEdit(self, itemKey, item):
        """
            Edit an item
        """

        while (True):
            # Check then set auto lock timer
            self.checkThenSetAutoLockTimer()

            print()
            while True:
                try:
                    command = self.input(
                        'Choose what you would like to edit [(c)ategory / (n)ame / (l)ogin / (p)assword / n(o)tes / (b)ack to Vault]: ')
                    break
                except KeyboardInterrupt as e:
                    # Back to menu if user cancels
                    print()
                    return
                except Exception as e:  # Other Exception
                    print()
                    pass

            # Ensure the input is lowercased
            command = command.lower()

            # Action based on command
            if command == 'c':  # Edit category
                self.editItemInput(itemKey, 'category',
                                   self.categoryName(item['category']))
                return
            elif command == 'n':  # Edit name
                self.editItemInput(itemKey, 'name', item['name'])
                return
            elif command == 'l':  # Edit login
                self.editItemInput(itemKey, 'login', item['login'])
                return
            elif command == 'p':  # Edit password
                self.editItemInput(itemKey, 'password', '')
                return
            elif command == 'o':  # Edit notes
                self.editItemInput(itemKey, 'notes', item['notes'])
                return
            elif command == 'b':  # Back to vault menu
                return

    def editItemInput(self, itemKey, fieldName, fieldCurrentValue):
        """
            Edit a field for an item
        """

        # Set auto lock timer (to prevent immediate re-locking)
        self.setAutoLockTimer()

        # Show current value
        if fieldName != 'password':
            print("* Current value: %s" % (fieldCurrentValue))

        try:
            # Get new value
            if fieldName == 'password':
                print('* Suggestion: %s' % (pwgenerator.generate()))
                fieldNewValue = getpass.getpass('* New password: ')
            elif fieldName == 'category':
                # Show categories
                print()
                print("* Available categories:")
                self.categoriesList()
                print()

                # Category ID
                fieldNewValue = self.input(
                    '* Choose a category number (or leave empty for none): ')

                if fieldNewValue != '':
                    if not self.categoryCheckId(fieldNewValue):
                        print('Invalid category. Please try again.')
                        self.editItemInput(
                            itemKey, fieldName, fieldCurrentValue)
            elif fieldName == 'notes':
                print('* Notes: (press [ENTER] twice to complete)')
                notes = []
                while True:
                    input_str = self.input("> ")
                    if input_str == "":
                        break
                    else:
                        notes.append(input_str)
                fieldNewValue = "\n".join(notes)
            else:
                fieldNewValue = self.input('* New %s: ' % (fieldName))
        except KeyboardInterrupt as e:
            # Back to menu if user cancels
            print()
            return

        # Update item
        item = self.vault['secrets'][itemKey][fieldName] = fieldNewValue

        # Debug
        # print(self.vault['secrets'][itemKey])

        # Save the vault
        self.saveVault()

        print('The item has been updated.')

    def itemDelete(self, itemKey):
        """
            Delete an item
        """

        try:
            # Get item
            item = self.vault['secrets'][itemKey]

            # Show item
            print()
            if confirm('Confirm deletion?', False):
                # Remove item
                self.vault['secrets'].pop(itemKey)

                # Save the vault
                self.saveVault()
        except Exception as e:
            print('Item does not exist.')

    def search(self):
        """
            Search items
        """

        # Set auto lock timer (to prevent immediate re-locking)
        self.setAutoLockTimer()

        print()
        while True:
            try:
                search = self.input('Enter search: ')
                break
            except KeyboardInterrupt as e:
                # Back to menu if user cancels
                print()
                return
            except Exception as e:  # Other Exception
                print()
                pass

        # Return to menu if search is empty
        if search == '':
            # Back to menu if user cancels
            print()
            print('Empty search!')
            return

        # To prevent fat-finger errors, the search menu will also respond to common commands
        if search in ['s', 'a', 'l', 'q']:  # Common commands
            return search
        elif search == 'b':  # Return to previous menu
            return

        if self.vault.get('secrets'):
            # Check if the user inputed an item number
            if search.isdigit():
                # Get item
                try:
                    # Will return an IndexError if the item does not exists
                    self.vault['secrets'][int(search)]
                    return self.get(int(search))
                except IndexError:
                    pass

            # Iterate thru the items
            results = []
            searchResultItems = {}
            searchResultItemNumber = 0
            for i, item in enumerate(self.vault['secrets']):
                # Search in name, login and notes
                if search.upper() in item['name'].upper() or \
                        search.upper() in item['login'].upper() or \
                        search.upper() in item['notes'].upper() or \
                        search.upper() in self.categoryName(item['category']).upper():
                    # Increment search result item number
                    searchResultItemNumber += 1

                    # Set search result value
                    searchResultItems[searchResultItemNumber] = i

                    # Add item to search results
                    results.append([
                        searchResultItemNumber,
                        i,
                        self.categoryName(item['category']),
                        item['name'],
                        item['login']
                    ])

            # If we have search results
            if len(results) == 1:  # Exactly one result
                # Get ID
                id = searchResultItems[1]

                # Load item
                return self.get(id)
            elif len(results) > 1:  # More than one result
                # Show results table
                from tabulate import tabulate
                print()
                print(tabulate(results, headers=[
                      '#', 'Item', 'Category', 'Name / URL', 'Login']))

                return self.searchResultSelection(searchResultItems)
            else:
                print('No results!')
        else:
            print("There are no secrets saved yet.")

    def searchResultSelection(self, searchResultItems):
        """
            Allow the user to select a search result or to go back to the main menu
        """

        # Set auto lock timer (to prevent immediate re-locking)
        self.setAutoLockTimer()

        print()
        while True:
            try:
                resultItem = self.input(
                    'Select a result # or type any key to go back to the main menu: ')
                break
            except KeyboardInterrupt as e:
                # Back to menu if user cancels
                print()
                return
            except Exception as e:  # Other Exception
                print()
                pass

        # Try getting an item or send user back to the main menu
        try:
            # Get item ID
            id = searchResultItems[int(resultItem)]

            return self.get(id)
        except Exception as e:
            # Back to menu if user cancels
            print()
            return

    def changeKey(self):
        """
            Replace vault key
            Will ask user to initially unlock the vault
            Then the user will input a new master key and the vault will be saved with the new key
        """

        # Unlock the vault with the existing key
        if self.vault is None:  # Except if the vault already unlocked
            self.unlock(False)  # `False` = don't load menu after unlocking

        # Choose a new key
        print()
        newMasterKey = getpass.getpass(
            lock_prefix() + 'Please choose a new master key:')
        newMasterKeyRepeat = getpass.getpass(
            lock_prefix() + 'Please confirm your new master key:')

        if len(newMasterKey) < 8:
            print()
            print('The master key should be at least 8 characters. Please try again!')
            print()
            # Try again
            self.changeKey()
        elif newMasterKey == newMasterKeyRepeat:
            # Override master key
            self.masterKey = newMasterKey

            # Save vault with new master key
            self.saveVault()

            print()
            print("Your master key has been updated.")
            self.unlock(False)
        else:
            print()
            print('The master key does not match its confirmation. Please try again!')
            print()
            # Try again
            self.changeKey()
