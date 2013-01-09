/*
 * Main kernel that runs test() routine defined in test.c
 *
 * Copyright Red Hat, Inc. 2013
 *
 * Authors:
 *  Igor Mammedov <imammedo@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 */

#include "main.h"

#define PORT 0x3f8   /* COM1 */

static unsigned char inbyte (unsigned short _port)
{
    unsigned char rv;
    __asm__ __volatile__ ("inb %1, %0" : "=a" (rv) : "dN" (_port));
    return rv;
}

static void outbyte (unsigned short _port, unsigned char _data)
{
    __asm__ __volatile__ ("outb %1, %0" : : "dN" (_port), "a" (_data));
}

static void init_serial() {
   outbyte(PORT + 1, 0x00);    // Disable all interrupts
   outbyte(PORT + 3, 0x80);    // Enable DLAB (set baud rate divisor)
   outbyte(PORT + 0, 0x03);    // Set divisor to 3 (lo byte) 38400 baud
   outbyte(PORT + 1, 0x00);    //                  (hi byte)
   outbyte(PORT + 3, 0x03);    // 8 bits, no parity, one stop bit
   outbyte(PORT + 2, 0xC7);    // Enable FIFO, clear them, with 14-byte threshold
   outbyte(PORT + 4, 0x0B);    // IRQs enabled, RTS/DSR set
}

static int is_empty() {
   return inbyte(PORT + 5) & 0x20;
}
 
static void putc_serial(char a) {
   while (is_empty() == 0);
 
   outbyte(PORT,a);
}

#define putchar putc_serial

void itoa (char *buf, int base, int d)
{
  char *p = buf;
  char *p1, *p2;
  unsigned long ud = d;
  int divisor = 10;
  
  /* If %d is specified and D is minus, put `-' in the head.  */
  if (base == 'd' && d < 0)
    {
      *p++ = '-';
      buf++;
      ud = -d;
    }
  else if (base == 'x')
    divisor = 16;

  /* Divide UD by DIVISOR until UD == 0.  */
  do
    {
      int remainder = ud % divisor;
      
      *p++ = (remainder < 10) ? remainder + '0' : remainder + 'a' - 10;
    }
  while (ud /= divisor);

  /* Terminate BUF.  */
  *p = 0;
  
  p1 = buf;
  p2 = p - 1;
  while (p1 < p2)
    {
      char tmp = *p1;
      *p1 = *p2;
      *p2 = tmp;
      p1++;
      p2--;
    }
}

void printf (const char *format, ...)
{
  char **arg = (char **) &format;
  int c;
  char buf[20];
  
  arg++;
  
  while ((c = *format++) != 0)
    {
      if (c != '%')
        putchar (c);
      else
        {
          char *p;
          
          c = *format++;
          switch (c)
            {
            case 'd':
            case 'u':
            case 'x':
              itoa (buf, c, *((int *) arg++));
              p = buf;
              goto string;
              break;

            case 's':
              p = *arg++;
              if (p == 0)
                p = "(null)";

            string:
              while (*p)
                putchar (*p++);
              break;

            default:
              putchar (*((int *) arg++));
              break;
            }
        }
    }
}

void cmain (unsigned long magic, unsigned long addr)
{

  init_serial();
  printf ("==START TEST==\n");
  test();
  printf ("==END TEST==\n");
}
