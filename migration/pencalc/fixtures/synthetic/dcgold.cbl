       IDENTIFICATION DIVISION.
       PROGRAM-ID. DCGOLD.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT GIN  ASSIGN TO "dcin.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT GOT  ASSIGN TO "dcout.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  GIN.
       01  GIN-REC                 PIC X(10).
       FD  GOT.
       01  GOT-REC                 PIC X(40).
       WORKING-STORAGE SECTION.
       01  EOFSW                   PIC X VALUE "N".
       01  OL.
           05  OL-JUL              PIC 9(07).
           05  FILLER              PIC X VALUE ",".
           05  OL-GREG             PIC 9(08).
           05  FILLER              PIC X VALUE ",".
           05  OL-RC               PIC X.
           05  FILLER              PIC X(22) VALUE SPACES.
       01  DC-PARM.
           05  DCP-FUNC            PIC X(01).
           05  DCP-GREG            PIC 9(08).
           05  DCP-JUL             PIC 9(07).
           05  DCP-RC              PIC X(01).
           05  DCP-RSV             PIC X(07).
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT GIN OUTPUT GOT
           PERFORM UNTIL EOFSW = "Y"
               READ GIN
                   AT END MOVE "Y" TO EOFSW
                   NOT AT END PERFORM 1000-ONE
               END-READ
           END-PERFORM
           CLOSE GIN GOT
           STOP RUN.
       1000-ONE.
           MOVE "G" TO DCP-FUNC
           MOVE GIN-REC(1:7) TO DCP-JUL
           MOVE ZERO TO DCP-GREG
           MOVE SPACE TO DCP-RC
           CALL "DATCNV" USING DC-PARM
           MOVE DCP-JUL TO OL-JUL
           MOVE DCP-GREG TO OL-GREG
           MOVE DCP-RC TO OL-RC
           WRITE GOT-REC FROM OL
           END-WRITE.
