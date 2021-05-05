import pyautogui
import time


def save_ad():
    print(pyautogui.size())
    print(pyautogui.position())
    
    print(pyautogui.position())
    pyautogui.moveTo(1347, 454)
    pyautogui.click()
    time.sleep(1)
    pyautogui.moveTo(1313, 684)
    pyautogui.scroll(-90)
    pyautogui.click()
    time.sleep(3)
    pyautogui.moveTo(528, 105)
    pyautogui.click()
    pyautogui.hotkey('ctrl','a')
    pyautogui.typewrite('http://google.com',interval=0.25)
    pyautogui.press('enter')
    time.sleep(5)

if __name__ == '__main__':
    for i in range(1,200):
        save_ad()
        print("Done %s" % i)
    print("Done")

