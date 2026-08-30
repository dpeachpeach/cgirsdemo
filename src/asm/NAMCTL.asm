NAMCTL   TITLE 'BMF NAME CONTROL DERIVATION - ENTITY RUN'
***********************************************************************
*                                                                     *
*  NAMCTL   DERIVE FOUR BYTE NAME CONTROL FROM AN ENTITY NAME.        *
*                                                                     *
*  LINKAGE  STANDARD.  R1 -> PARAMETER LIST, WORD 0 -> PARM AREA.     *
*           R13 -> CALLER SAVE AREA.  R14 RETURN.  R15 ENTRY/RC.      *
*                                                                     *
*  RETURN   0  NAME CONTROL RETURNED                                  *
*           8  NAME UNUSABLE, FIELD SET TO BLANKS                     *
*                                                                     *
*  CHG 09/84  ORIGINAL                                                *
*  CHG 02/86  ARTICLE HANDLING                                        *
*                                                                     *
***********************************************************************
         SPACE 1
R0       EQU   0
R1       EQU   1
R2       EQU   2
R3       EQU   3
R4       EQU   4
R5       EQU   5
R6       EQU   6
R7       EQU   7
R8       EQU   8
R9       EQU   9
R10      EQU   10
R11      EQU   11
R12      EQU   12
R13      EQU   13
R14      EQU   14
R15      EQU   15
         SPACE 1
NAMCTL   CSECT
         STM   R14,R12,12(R13)          SAVE CALLERS REGISTERS
         LR    R12,R15                  ENTRY ADDRESS TO BASE
         USING NAMCTL,R12
         LA    R11,SAVEA
         ST    R13,4(,R11)              CHAIN BACKWARD
         ST    R11,8(,R13)              CHAIN FORWARD
         LR    R13,R11
         SPACE 1
         L     R2,0(,R1)                A(PARM AREA)
         USING PARM,R2
         SPACE 1
         MVI   PF39,C'0'                RC ZERO
         MVC   PF35(4),BLANKS           CLEAR RETURN FIELD
         MVC   WORK(35),PF00            COPY THE NAME
         TR    WORK(35),UCTAB           FOLD TO UPPER CASE
         SPACE 1
***********************************************************************
*  COUNT BLANK DELIMITED WORDS.  R6 HOLDS THE COUNT.                  *
***********************************************************************
         SR    R6,R6
         LA    R3,WORK
         LA    R4,35
         MVI   PREV,C' '
CNT010   CLI   0(R3),C' '
         BE    CNT020
         CLI   PREV,C' '
         BNE   CNT020
         LA    R6,1(,R6)
CNT020   MVC   PREV,0(R3)
         LA    R3,1(,R3)
         BCT   R4,CNT010
         LTR   R6,R6
         BZ    ERR010                   NOTHING USABLE
         SPACE 1
***********************************************************************
*  AN ARTICLE IS BRACKETED OUT OF THE NAME CONTROL.                   *
***********************************************************************
         CLC   WORK(4),THE
         BNE   SQZ000
         MVC   WORK(31),WORK+4
         MVC   WORK+31(4),BLANKS
         SPACE 1
***********************************************************************
*  SQUEEZE OUT BLANKS AND PUNCTUATION USING TRT.  THE TABLE FLAGS     *
*  ANY BYTE THAT IS NOT TO BE CARRIED INTO THE NAME CONTROL.          *
***********************************************************************
SQZ000   MVC   OUT(4),BLANKS
         LA    R3,WORK
         LA    R4,35
         LA    R5,OUT
         SR    R7,R7
SQZ010   SR    R0,R0
         IC    R0,0(,R3)
         LA    R8,DROPTB
         AR    R8,R0
         CLI   0(R8),X'FF'
         BE    SQZ020                   DROP THIS BYTE
         MVC   0(1,R5),0(R3)
         LA    R5,1(,R5)
         LA    R7,1(,R7)
         CH    R7,=H'4'
         BE    SQZ030
SQZ020   LA    R3,1(,R3)
         BCT   R4,SQZ010
SQZ030   LTR   R7,R7
         BZ    ERR010
         MVC   PF35(4),OUT
         B     EXIT
         SPACE 1
ERR010   MVI   PF39,C'8'
         MVC   PF35(4),BLANKS
         SPACE 1
EXIT     L     R13,4(,R13)
         LM    R14,R12,12(R13)
         SR    R15,R15
         BR    R14
         SPACE 1
SAVEA    DS    18F
WORK     DS    CL35
OUT      DS    CL4
PREV     DS    CL1
BLANKS   DC    CL8' '
THE      DC    CL4'THE '
         SPACE 1
***********************************************************************
*  DROPTB  X'FF' MARKS BLANK, COMMA, PERIOD, APOSTROPHE AND HYPHEN.   *
***********************************************************************
DROPTB   DC    256X'00'
         ORG   DROPTB+X'40'
         DC    X'FF'                    BLANK
         ORG   DROPTB+X'4B'
         DC    X'FF'                    PERIOD
         ORG   DROPTB+X'5D'
         DC    X'FF'                    APOSTROPHE
         ORG   DROPTB+X'60'
         DC    X'FF'                    HYPHEN
         ORG   DROPTB+X'6B'
         DC    X'FF'                    COMMA
         ORG
         SPACE 1
UCTAB    DC    256AL1(*-UCTAB)
         ORG   UCTAB+X'81'
         DC    X'C1C2C3C4C5C6C7C8C9'
         ORG   UCTAB+X'91'
         DC    X'D1D2D3D4D5D6D7D8D9'
         ORG   UCTAB+X'A2'
         DC    X'E2E3E4E5E6E7E8E9'
         ORG
         SPACE 1
***********************************************************************
*  PARAMETER AREA.  48 BYTES.  MAPPED BY DISPLACEMENT.                *
***********************************************************************
PARM     DSECT
PF00     DS    CL35                     +0
PF35     DS    CL4                      +35
PF39     DS    CL1                      +39
PF40     DS    CL8                      +40
         SPACE 1
         END   NAMCTL
