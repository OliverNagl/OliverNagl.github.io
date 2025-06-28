## Douple solution Jigsaw Puzzles
Many types of Jigsaw puzzles have multiple solutions trivially, where one could place any piece at any place, just
without actually making a picture. Then there is the kind of jigsaw puzzle where the only solution that is possible is the 
arrangment showing the correct picture. With the recent success of diffusion based image generation Ryan Burgert (etal.) 
where able to produce illusions in which a jigsaw puzzle, that can be solved physically in exactly 2 ways, also has two 
different non trivial image solutions. (https://diffusionillusions.com/) Their website hosts some examples using the double solution
created by Matt Parker for this purpose (https://www.youtube.com/watch?v=b5nElEbbnfU).

The creation of a set of Jigs that can be solved in exactly 2 (non-trivial) ways is not an easy problem. Therefore Matt Parker`s 
brute force solution of creating such sets of jigs is limited to jigsaws of about 6 x 6. 
In this little code project I did over my last winter holidays I tried to find a algorithm that would be able to go to larger 
grids of jigs. The code is super crap and full of bugs. But it works, I was able to extend the possible dimension that one can create
non trivial double solution jigsaw up to ca. 15x15. (on a Laptop running overnight).

## Finished puzzles
Here you can see one of the mappings that where created using this code, these are the only two solutions possible for these connections:
<img src="jigsaw_puzzle_mapped_14.svg" alt="Puzzle Solution 2" width="400"/>
<img src="jigsaw_puzzle_14.svg" alt="Puzzle Solution 1" width="400"/>



And here you see it after applying the diffusion illusion algorithm on it:
<img src="Puzzle_Solutions_after_diffusion/VanGogh61.png" alt="Puzzle Solution 1" width="400"/>
<img src="Puzzle_Solutions_after_diffusion/VanGogh62.png" alt="Puzzle Solution 2" width="400"/>


As one can see the Diffusion still has a hard time mapping two pictures onto the two solutions. (as can be expected from
two such complex pictures on a 15x15 puzzle piece, especially since the size is also limited to 512x512 pixel)

## How does it work?
My solution combines two approaches:
1) Create a random valid Jigsaw with a random (decided) number of edges already initialized
2) Encoding the system into a SAT solvable boolean value problem, each jig has a variable for each connection 
type that can be assigned to each of the edges (4 x num_conn_types) variables. As well as a boolean for any position 
on the grid where it can be placed. Then there is a list of constraints added such that every piece from the 
valid jigsaw must exist, can only be placed once, needs to connect with the right edges to its neighbours, etc.
By adding a negative clause disallowing the original puzzle one forces the pySAT solver to find a second solution. 
3) Now there need to be some additional constraints such as: disallowing global rotation (otherwise rotating the 
whole puzzle by 90 degrees would be a solution) Heuristically disallowing certain patterns (such as swapping rows etc.)
This is a bit of a art and I havent figured out the best configuration of the hyperparameters (like initial puzzle edges, how many patterns should be dissallowed, how many connection types should exist etc.)
Interestingly there is a paper on what the ideal number of puzzle edge types there should be for a second solution to be probably. (the paper is not exactly applicable as it doesnt deal with the flat end pieces of the puzzle, but its a starting point.) There is even a paper that might be usefull for generating initial puzzles. This is not implemented though.

[1] Anders Martinsson. *A linear threshold for uniqueness of solutions to random jigsaw puzzles*.  
Combinatorics, Probability and Computing, 28(2), 2019.  
[arXiv:1701.04813](https://arxiv.org/abs/1701.04813) 

[2] Anders Martinsson. *Shotgun edge assembly of random jigsaw puzzles*.  
arXiv preprint, 2016.  
[arXiv:1605.03086](https://arxiv.org/abs/1605.03086)


4) Having set enough heuristical constraints the solver will only find "nice" scrambled second solutions.
5) negate the second solution and make sure that there is no 3rd solution. 
6) Plot the Mapped (second) solution onto a UV-identity map to be able to run the diffusion illusion code.
7) enjoy.

## TODO:
Explain the constraints/code better.
Implement the Shotgun edge assembly as initial.
Comment code
