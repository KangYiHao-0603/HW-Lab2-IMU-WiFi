/*
 * config.h
 *
 *  Created on: 19 feb 2021
 *      Author: Raul Rosa
 */

#ifndef INC_CONFIG_H_
#define INC_CONFIG_H_



#define SSID "9487"            //name of the wifi
#define PSW "11111111"         //Wifi Password
#define IPgw "172.20.10.2"  //IP address of your PC / RPi running host_gui.py
#define PORTgw "8080"         //Port of host_gui.py (default 8080)
#define deviceid "456"          //the whitelist of the device in the GW
#define TIME_INTERVAL 50   //extra delay in ms between two samples (each HTTP POST already takes time)







#endif /* INC_CONFIG_H_ */
